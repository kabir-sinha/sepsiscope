"""Download the PhysioNet/CinC 2019 training files from the official public S3 bucket.

Safety properties (each one has a test):

* Only one host is ever contacted, over HTTPS, with TLS verification on, no
  credentials, no proxies/netrc from the environment and no redirects.
* The bucket listing is parsed with ``defusedxml`` (never stdlib XML on network data).
* A listed key is only used if it matches the expected file-name pattern, and the
  save path built from it must stay inside the raw-data folder.
* The listing's own counts are checked before any file is downloaded.
* Each response is capped (1 MB) and aborted if it exceeds the listed size.
* Files are written to a temp file, checked (size + MD5 against the S3 ETag), then
  renamed atomically. Files already present and correct are skipped (resumable).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import httpx
from defusedxml import ElementTree as SafeET

ALLOWED_HOST = "physionet-open.s3.amazonaws.com"
BASE_URL = f"https://{ALLOWED_HOST}"
PREFIX = "challenge-2019/1.0.0/training/"
# Where the files land under the raw-data root (mirrors the bucket layout).
LOCAL_SUBDIR = Path("physionet-challenge-2019") / "1.0.0" / "training"
KEY_RE = re.compile(r"^challenge-2019/1\.0\.0/training/(training_set[AB])/(p\d{6}\.psv)$")
MD5_RE = re.compile(r"^[0-9a-f]{32}$")
EXPECTED_COUNTS: dict[str, int] = {"training_setA": 20_336, "training_setB": 20_000}

MAX_FILE_BYTES = 1_000_000  # hard cap per response; real files are a few kB
MAX_CONCURRENCY = 8
MAX_ATTEMPTS = 4
S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


class DownloadError(RuntimeError):
    """Raised when the listing or a file cannot be trusted."""


@dataclass(frozen=True)
class RemoteObject:
    key: str
    size: int
    etag: str  # quotes stripped

    @property
    def subset(self) -> str:
        match = KEY_RE.match(self.key)
        if match is None:  # pragma: no cover - objects are only built from matching keys
            raise DownloadError(f"unexpected key: {self.key!r}")
        return match.group(1)

    @property
    def filename(self) -> str:
        match = KEY_RE.match(self.key)
        if match is None:  # pragma: no cover
            raise DownloadError(f"unexpected key: {self.key!r}")
        return match.group(2)

    @property
    def md5_verifiable(self) -> bool:
        """A single-part upload's ETag is the MD5; multipart ETags contain '-'."""
        return MD5_RE.match(self.etag) is not None


@dataclass(frozen=True)
class DownloadReport:
    listed: int
    skipped_keys: tuple[str, ...]  # listed keys that are not patient files
    downloaded: int
    already_present: int
    unverifiable: tuple[str, ...]  # keys whose ETag is not a plain MD5
    seconds: float


def _only_allowed_host(request: httpx.Request) -> None:
    if request.url.scheme != "https" or request.url.host != ALLOWED_HOST:
        raise DownloadError(f"refusing to contact {request.url.scheme}://{request.url.host}")


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """HTTPS-only client: TLS verified, no redirects, no env proxies/netrc, no auth."""
    return httpx.Client(
        base_url=BASE_URL,
        verify=True,
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(30.0, connect=10.0),
        limits=httpx.Limits(max_connections=MAX_CONCURRENCY),
        event_hooks={"request": [_only_allowed_host]},
        transport=transport,
    )


def parse_listing(xml: bytes) -> tuple[list[RemoteObject], list[str], str | None]:
    """Parse one ListObjectsV2 page -> (patient objects, other keys, next token)."""
    root = SafeET.fromstring(xml)
    objects: list[RemoteObject] = []
    other: list[str] = []
    for node in root.findall(f"{S3_NS}Contents"):
        key = node.findtext(f"{S3_NS}Key") or ""
        size_text = node.findtext(f"{S3_NS}Size") or ""
        etag = (node.findtext(f"{S3_NS}ETag") or "").strip('"')
        if KEY_RE.match(key) is None:
            other.append(key)
            continue
        if not size_text.isdigit():
            raise DownloadError(f"listing has a non-numeric size for {key!r}")
        objects.append(RemoteObject(key=key, size=int(size_text), etag=etag))
    truncated = (root.findtext(f"{S3_NS}IsTruncated") or "false").lower() == "true"
    token = root.findtext(f"{S3_NS}NextContinuationToken") if truncated else None
    if truncated and not token:
        raise DownloadError("listing is truncated but has no continuation token")
    return objects, other, token


def list_objects(client: httpx.Client) -> tuple[list[RemoteObject], list[str]]:
    """List every object under the training prefix, following continuation tokens."""
    objects: list[RemoteObject] = []
    other: list[str] = []
    token: str | None = None
    for _ in range(1_000):  # far more pages than the bucket can have
        params = {"list-type": "2", "prefix": PREFIX}
        if token:
            params["continuation-token"] = token
        response = client.get("/", params=params)
        response.raise_for_status()
        page, page_other, token = parse_listing(response.content)
        objects.extend(page)
        other.extend(page_other)
        if token is None:
            return objects, other
    raise DownloadError("listing did not terminate")


def check_listing(
    objects: Iterable[RemoteObject], expected_counts: dict[str, int] = EXPECTED_COUNTS
) -> None:
    """Fail before downloading anything if the listing itself looks wrong."""
    items = list(objects)
    keys = [o.key for o in items]
    if len(keys) != len(set(keys)):
        raise DownloadError("listing contains duplicate keys")
    counts = Counter(o.subset for o in items)
    if dict(counts) != expected_counts:
        raise DownloadError(f"listing counts {dict(counts)} != expected {expected_counts}")
    for obj in items:
        if not 0 < obj.size <= MAX_FILE_BYTES:
            raise DownloadError(f"listed size {obj.size} out of range for {obj.key!r}")


def safe_path(raw_root: Path, obj: RemoteObject) -> Path:
    """Build the save path from the key and prove it stays inside ``raw_root``."""
    root = raw_root.resolve()
    target = (root / LOCAL_SUBDIR / obj.subset / obj.filename).resolve()
    if not target.is_relative_to(root):
        raise DownloadError(f"refusing to write outside the raw-data folder: {obj.key!r}")
    return target


def md5_of(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)  # integrity check against the S3 ETag
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_complete(path: Path, obj: RemoteObject) -> bool:
    """True if the local file exists with the listed size (and MD5 when verifiable)."""
    if not path.is_file() or path.stat().st_size != obj.size:
        return False
    return not obj.md5_verifiable or md5_of(path) == obj.etag


def _fetch_once(client: httpx.Client, obj: RemoteObject, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - closed in the finally below
        dir=dest.parent, prefix=".part-", delete=False
    )
    tmp = Path(handle.name)
    try:
        received = 0
        digest = hashlib.md5(usedforsecurity=False)
        with client.stream("GET", f"/{obj.key}") as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                received += len(chunk)
                if received > obj.size or received > MAX_FILE_BYTES:
                    raise DownloadError(f"{obj.key!r} is larger than its listed size")
                digest.update(chunk)
                handle.write(chunk)
        handle.close()
        if received != obj.size:
            raise DownloadError(f"{obj.key!r}: got {received} bytes, listed {obj.size}")
        if obj.md5_verifiable and digest.hexdigest() != obj.etag:
            raise DownloadError(f"{obj.key!r}: MD5 does not match the S3 ETag")
        os.replace(tmp, dest)  # noqa: PTH105 - atomic rename
    finally:
        handle.close()
        tmp.unlink(missing_ok=True)


def fetch(
    client: httpx.Client,
    obj: RemoteObject,
    dest: Path,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Download one object with retries and exponential backoff."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            _fetch_once(client, obj, dest)
            return
        except (httpx.HTTPError, DownloadError):
            if attempt == MAX_ATTEMPTS:
                raise
            sleep(0.5 * 2 ** (attempt - 1))


def write_manifest(raw_root: Path, objects: Iterable[RemoteObject]) -> str:
    """Write MANIFEST.json (key, size, md5) and return the SHA-256 of its content."""
    rows: list[dict[str, object]] = [
        {"key": o.key, "size": o.size, "md5": o.etag} for o in sorted(objects, key=lambda o: o.key)
    ]
    payload = json.dumps(rows, indent=0, sort_keys=True).encode("utf-8")
    (raw_root / "MANIFEST.json").write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def download_all(
    raw_root: Path,
    *,
    transport: httpx.BaseTransport | None = None,
    expected_counts: dict[str, int] = EXPECTED_COUNTS,
    concurrency: int = MAX_CONCURRENCY,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[DownloadReport, str]:
    """List, check, download what is missing and write the manifest."""
    started = time.monotonic()
    raw_root.mkdir(parents=True, exist_ok=True)
    for stale in raw_root.rglob(".part-*"):  # left behind by an interrupted run
        stale.unlink()
    with make_client(transport) as client:
        objects, other = list_objects(client)
        check_listing(objects, expected_counts)
        todo = [(o, safe_path(raw_root, o)) for o in objects]
        missing = [(o, p) for o, p in todo if not is_complete(p, o)]
        workers = max(1, min(concurrency, MAX_CONCURRENCY))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(lambda pair: fetch(client, pair[0], pair[1], sleep), missing))
    not_ok = [o.key for o, p in todo if not is_complete(p, o)]
    if not_ok:
        raise DownloadError(f"{len(not_ok)} files failed verification, e.g. {not_ok[:3]}")
    manifest_sha = write_manifest(raw_root, objects)
    report = DownloadReport(
        listed=len(objects),
        skipped_keys=tuple(sorted(other)),
        downloaded=len(missing),
        already_present=len(todo) - len(missing),
        unverifiable=tuple(sorted(o.key for o in objects if not o.md5_verifiable)),
        seconds=time.monotonic() - started,
    )
    return report, manifest_sha
