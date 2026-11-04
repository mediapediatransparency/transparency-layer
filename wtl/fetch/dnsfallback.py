"""Name lookup fallback for this tool's own process.

On some machines a network filter's extension breaks the operating system's resolver for
command-line programs, while the configured DNS server itself still answers. When the normal
lookup fails, this asks the machine's own configured DNS server directly (with `dig`) and uses
its answer. Filtering is unchanged: the answer comes from the same server the system uses, so a
host that server blocks stays blocked. Nothing outside this process is changed.
"""

import functools
import re
import socket
import subprocess

_orig = socket.getaddrinfo
_installed = False


@functools.lru_cache(maxsize=1)
def _nameserver() -> str | None:
    try:
        out = subprocess.run(["scutil", "--dns"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"nameserver\[0\]\s*:\s*([0-9.]+)", out)
    return m.group(1) if m else None


@functools.lru_cache(maxsize=20000)
def _dig(host: str) -> tuple[str, ...]:
    ns = _nameserver()
    if not ns:
        return ()
    try:
        out = subprocess.run(["dig", "+short", "+time=5", "+tries=2", f"@{ns}", host, "A"],
                             capture_output=True, text=True, timeout=25).stdout
    except (OSError, subprocess.SubprocessError):
        return ()
    return tuple(x for x in out.split() if re.fullmatch(r"(\d{1,3}\.){3}\d{1,3}", x))


_failed = set()   # hosts the system resolver already failed on: go straight to the fallback


def _getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    def fallback():
        ips = _dig(host)
        if not ips:
            raise socket.gaierror(socket.EAI_NONAME, f"{host}: not resolved by the configured DNS server")
        return [(socket.AF_INET, type or socket.SOCK_STREAM, proto or socket.IPPROTO_TCP, "",
                 (ip, port if isinstance(port, int) else int(port or 0))) for ip in ips]
    if isinstance(host, str) and host in _failed:
        return fallback()
    try:
        return _orig(host, port, family, type, proto, flags)
    except socket.gaierror:
        if not isinstance(host, str) or re.fullmatch(r"[0-9.:]+", host):
            raise
        _failed.add(host)
        return fallback()


def install() -> None:
    global _installed
    if not _installed:
        socket.getaddrinfo = _getaddrinfo
        _installed = True
