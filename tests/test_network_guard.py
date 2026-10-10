"""The autouse guard in conftest.py: no DNS, no TCP/UDP connections, AF_UNIX still works."""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path

import httpx
import pytest
from conftest import NetworkBlockedError


def test_dns_lookup_is_blocked() -> None:
    with pytest.raises(NetworkBlockedError, match="resolve"):
        socket.getaddrinfo("example.com", 443)


@pytest.mark.parametrize("family", [socket.AF_INET, socket.AF_INET6])
def test_connect_and_connect_ex_are_blocked(family: socket.AddressFamily) -> None:
    address = ("127.0.0.1", 9) if family == socket.AF_INET else ("::1", 9)
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        with pytest.raises(NetworkBlockedError, match="connect"):
            sock.connect(address)
        with pytest.raises(NetworkBlockedError, match="connect"):
            sock.connect_ex(address)


def test_udp_connect_is_blocked() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock,
        pytest.raises(NetworkBlockedError),
    ):
        sock.connect(("127.0.0.1", 53))


@pytest.mark.parametrize("url", ["https://example.com/", "https://127.0.0.1:9/"])
def test_httpx_sync_fails_under_the_guard(url: str) -> None:
    with httpx.Client(trust_env=False) as client, pytest.raises(NetworkBlockedError):
        client.get(url)


def _contains_block(exc: BaseException) -> bool:
    """True if the error is the guard's, directly or inside an exception group."""
    if isinstance(exc, NetworkBlockedError):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return any(_contains_block(inner) for inner in exc.exceptions)
    return False


@pytest.mark.parametrize("url", ["https://example.com/", "https://127.0.0.1:9/"])
def test_httpx_async_fails_under_the_guard(url: str) -> None:
    async def fetch() -> None:
        async with httpx.AsyncClient(trust_env=False) as client:
            await client.get(url)

    with pytest.raises(BaseException) as excinfo:
        asyncio.run(fetch())
    assert _contains_block(excinfo.value)


def test_unix_domain_sockets_still_work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # short relative path: socket paths are length-limited
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind("guard.sock")
        server.listen(1)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect("guard.sock")
            conn, _ = server.accept()
            with conn:
                client.sendall(b"ok")
                assert conn.recv(2) == b"ok"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            assert client.connect_ex("guard.sock") == 0
