from __future__ import annotations

import socket

import pytest

from scripts.run_http import _is_port_free, find_free_port

HOST = "127.0.0.1"


def _free_ephemeral_port() -> int:
    """A real, currently-free port, picked by the OS (bind to 0) -- not a
    hardcoded number that could collide with something else already
    running on the machine these tests run on."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        port: int = sock.getsockname()[1]
        return port


def test_find_free_port_returns_the_preferred_port_when_it_is_free() -> None:
    preferred = _free_ephemeral_port()

    assert find_free_port(HOST, preferred) == preferred


def test_find_free_port_walks_forward_past_a_real_occupied_port() -> None:
    # A real bound socket, not a mock -- matches this repo's own preference
    # for exercising real infrastructure wherever it's cheap enough to.
    preferred = _free_ephemeral_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupier:
        occupier.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        occupier.bind((HOST, preferred))
        occupier.listen(1)

        found = find_free_port(HOST, preferred)

        assert found != preferred
        assert found > preferred
        # And it's genuinely free -- not just "not the occupied one".
        assert _is_port_free(HOST, found)


def test_find_free_port_skips_multiple_consecutive_occupied_ports() -> None:
    preferred = _free_ephemeral_port()
    occupiers = []
    try:
        for offset in range(3):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((HOST, preferred + offset))
            sock.listen(1)
            occupiers.append(sock)

        found = find_free_port(HOST, preferred)

        assert found == preferred + 3
    finally:
        for sock in occupiers:
            sock.close()


def test_find_free_port_raises_when_every_candidate_in_range_is_occupied() -> None:
    preferred = _free_ephemeral_port()
    occupiers = []
    try:
        for offset in range(2):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((HOST, preferred + offset))
            sock.listen(1)
            occupiers.append(sock)

        with pytest.raises(SystemExit, match="No free port found"):
            find_free_port(HOST, preferred, max_attempts=2)
    finally:
        for sock in occupiers:
            sock.close()


def test_is_port_free_reflects_real_socket_state() -> None:
    preferred = _free_ephemeral_port()
    assert _is_port_free(HOST, preferred) is True

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupier:
        occupier.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        occupier.bind((HOST, preferred))
        occupier.listen(1)

        assert _is_port_free(HOST, preferred) is False
