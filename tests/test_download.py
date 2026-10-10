"""Downloader tests against a mocked HTTP transport: no network is ever used."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from sepsiscope.data import download as dl

NS = "http://s3.amazonaws.com/doc/2006-03-01/"
PREFIX = dl.PREFIX


def _md5(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def _page(items: list[tuple[str, int, str]], token: str | None = None) -> bytes:
    contents = "".join(
        f"<Contents><Key>{k}</Key><Size>{s}</Size><ETag>&quot;{e}&quot;</ETag></Contents>"
        for k, s, e in items
    )
    tail = (
        f"<IsTruncated>true</IsTruncated><NextContinuationToken>{token}</NextContinuationToken>"
        if token
        else "<IsTruncated>false</IsTruncated>"
    )
    return f'<ListBucketResult xmlns="{NS}">{contents}{tail}</ListBucketResult>'.encode()


class FakeBucket:
    """A tiny in-memory S3 bucket served through httpx.MockTransport."""

    def __init__(self, files: dict[str, bytes], page_size: int = 2) -> None:
        self.files = dict(files)
        self.etags = {k: _md5(v) for k, v in files.items()}
        self.sizes = {k: len(v) for k, v in files.items()}
        self.page_size = page_size
        self.gets: list[str] = []
        self.extra_keys: list[tuple[str, int, str]] = []
        self.fail_first: dict[str, int] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.url.scheme == "https"
        assert request.url.host == dl.ALLOWED_HOST
        assert "authorization" not in request.headers
        if request.url.path == "/":
            assert request.url.params["prefix"] == PREFIX
            keys = sorted(self.files)
            start = int(request.url.params.get("continuation-token", "0"))
            chunk = keys[start : start + self.page_size]
            nxt = start + self.page_size
            items = [(k, self.sizes[k], self.etags[k]) for k in chunk]
            if nxt >= len(keys):
                return httpx.Response(200, content=_page(items + self.extra_keys))
            return httpx.Response(200, content=_page(items, token=str(nxt)))
        key = request.url.path.lstrip("/")
        self.gets.append(key)
        if self.fail_first.get(key, 0) > 0:
            self.fail_first[key] -= 1
            return httpx.Response(503)
        return httpx.Response(200, content=self.files[key])

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


def _key(subset: str, number: int) -> str:
    return f"{PREFIX}training_set{subset}/p{number:06d}.psv"


@pytest.fixture
def bucket() -> FakeBucket:
    return FakeBucket(
        {
            _key("A", 1): b"HR|SepsisLabel\n80|0\n",
            _key("A", 2): b"HR|SepsisLabel\n81|0\n82|1\n",
            _key("A", 3): b"HR|SepsisLabel\n90|0\n",
            _key("B", 100001): b"HR|SepsisLabel\n70|0\n",
            _key("B", 100002): b"HR|SepsisLabel\n71|1\n",
        }
    )


COUNTS = {"training_setA": 3, "training_setB": 2}


def _run(bucket: FakeBucket, root: Path) -> tuple[dl.DownloadReport, str]:
    return dl.download_all(
        root, transport=bucket.transport, expected_counts=COUNTS, sleep=lambda _s: None
    )


def test_download_paginates_verifies_and_writes_manifest(
    bucket: FakeBucket, tmp_path: Path
) -> None:
    report, sha = _run(bucket, tmp_path)
    assert (report.listed, report.downloaded, report.already_present) == (5, 5, 0)
    assert report.unverifiable == ()
    for key, data in bucket.files.items():
        local = tmp_path / dl.LOCAL_SUBDIR / Path(key).parent.name / Path(key).name
        assert local.read_bytes() == data
    manifest = (tmp_path / "MANIFEST.json").read_bytes()
    assert hashlib.sha256(manifest).hexdigest() == sha
    rows = json.loads(manifest)
    assert [r["key"] for r in rows] == sorted(bucket.files)
    assert rows[0]["md5"] == bucket.etags[rows[0]["key"]]
    assert not list(tmp_path.rglob(".part-*"))  # no temp files left behind


def test_resume_skips_complete_files_and_refetches_corrupt_ones(
    bucket: FakeBucket, tmp_path: Path
) -> None:
    _run(bucket, tmp_path)
    bucket.gets.clear()
    victim = tmp_path / dl.LOCAL_SUBDIR / "training_setA" / "p000002.psv"
    victim.write_bytes(b"x" * victim.stat().st_size)  # same size, wrong content
    report, _ = _run(bucket, tmp_path)
    assert (report.downloaded, report.already_present) == (1, 4)
    assert bucket.gets == [_key("A", 2)]
    assert victim.read_bytes() == bucket.files[_key("A", 2)]


def test_retries_then_succeeds(bucket: FakeBucket, tmp_path: Path) -> None:
    bucket.fail_first[_key("A", 1)] = 2
    report, _ = _run(bucket, tmp_path)
    assert report.downloaded == 5
    assert bucket.gets.count(_key("A", 1)) == 3


def test_etag_mismatch_fails_and_leaves_no_file(bucket: FakeBucket, tmp_path: Path) -> None:
    bucket.etags[_key("B", 100001)] = "0" * 32
    with pytest.raises(dl.DownloadError, match="MD5"):
        _run(bucket, tmp_path)
    assert not (tmp_path / dl.LOCAL_SUBDIR / "training_setB" / "p100001.psv").exists()
    assert not list(tmp_path.rglob(".part-*"))


def test_body_larger_than_listed_size_is_aborted(bucket: FakeBucket, tmp_path: Path) -> None:
    bucket.sizes[_key("A", 3)] -= 4
    with pytest.raises(dl.DownloadError, match="larger than its listed size"):
        _run(bucket, tmp_path)


def test_listing_count_mismatch_fails_before_any_download(
    bucket: FakeBucket, tmp_path: Path
) -> None:
    del bucket.files[_key("B", 100002)]
    with pytest.raises(dl.DownloadError, match="counts"):
        _run(bucket, tmp_path)
    assert bucket.gets == []


def test_oversized_listing_entry_fails_before_any_download(
    bucket: FakeBucket, tmp_path: Path
) -> None:
    bucket.sizes[_key("A", 1)] = dl.MAX_FILE_BYTES + 1
    with pytest.raises(dl.DownloadError, match="out of range"):
        _run(bucket, tmp_path)
    assert bucket.gets == []


def test_unexpected_keys_are_ignored_never_fetched(bucket: FakeBucket, tmp_path: Path) -> None:
    bucket.extra_keys = [
        (f"{PREFIX}index.html", 10, "a" * 32),
        (f"{PREFIX}training_setA/../../../evil.psv", 10, "b" * 32),
        (f"{PREFIX}training_setA/p000009.psv.exe", 10, "c" * 32),
    ]
    report, _ = _run(bucket, tmp_path)
    assert len(report.skipped_keys) == 3
    assert all(k in bucket.files for k in bucket.gets)
    assert not list(tmp_path.parent.rglob("evil.psv"))


def test_multipart_etag_is_reported_as_unverifiable(bucket: FakeBucket, tmp_path: Path) -> None:
    bucket.etags[_key("A", 1)] = "d41d8cd98f00b204e9800998ecf8427e-2"
    report, _ = _run(bucket, tmp_path)
    assert report.unverifiable == (_key("A", 1),)


def test_safe_path_stays_inside_root(tmp_path: Path) -> None:
    obj = dl.RemoteObject(_key("A", 7), 1, "a" * 32)
    assert dl.safe_path(tmp_path, obj).is_relative_to(tmp_path.resolve())


def test_safe_path_blocks_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "raw"
    (root / dl.LOCAL_SUBDIR).mkdir(parents=True)
    (root / dl.LOCAL_SUBDIR / "training_setA").symlink_to(outside, target_is_directory=True)
    with pytest.raises(dl.DownloadError, match="outside"):
        dl.safe_path(root, dl.RemoteObject(_key("A", 7), 1, "a" * 32))


def test_client_refuses_other_hosts_and_plain_http() -> None:
    def never(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("request should have been blocked")

    with dl.make_client(httpx.MockTransport(never)) as client:
        with pytest.raises(dl.DownloadError, match="refusing"):
            client.get("https://example.com/")
        with pytest.raises(dl.DownloadError, match="refusing"):
            client.get(f"http://{dl.ALLOWED_HOST}/")


def test_client_does_not_follow_redirects_or_use_env() -> None:
    client = dl.make_client(httpx.MockTransport(lambda r: httpx.Response(200)))
    assert client.follow_redirects is False
    assert client.trust_env is False
    client.close()


def test_listing_rejects_xml_entity_tricks() -> None:
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]>'
        b'<ListBucketResult xmlns="' + NS.encode() + b'"><Key>&lol;</Key></ListBucketResult>'
    )
    with pytest.raises(Exception, match=r"(?i)entit|forbidden"):
        dl.parse_listing(bomb)


def test_truncated_listing_without_token_fails() -> None:
    xml = f'<ListBucketResult xmlns="{NS}"><IsTruncated>true</IsTruncated></ListBucketResult>'
    with pytest.raises(dl.DownloadError, match="continuation"):
        dl.parse_listing(xml.encode())


def test_stale_temp_files_are_removed(bucket: FakeBucket, tmp_path: Path) -> None:
    stale = tmp_path / dl.LOCAL_SUBDIR / "training_setA" / ".part-old"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"partial")
    _run(bucket, tmp_path)
    assert not stale.exists()


def test_real_network_is_blocked_in_tests(tmp_path: Path) -> None:
    with pytest.raises((AssertionError, httpx.HTTPError, dl.DownloadError)):
        dl.download_all(tmp_path, sleep=lambda _s: None)
    assert not (tmp_path / "MANIFEST.json").exists()
