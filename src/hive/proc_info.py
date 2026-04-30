"""Native process introspection helpers.

Darwin uses ``proc_pidinfo`` and Linux uses ``/proc/<pid>/fd`` so callers can
inspect short-lived open file handles without paying ``lsof`` process-spawn
latency on the hot path.
"""

from __future__ import annotations

import ctypes
import os
import sys
from functools import lru_cache
from pathlib import Path


class ProcInfoError(RuntimeError):
    """Base error for native process introspection failures."""


class ProcInfoUnavailable(ProcInfoError):
    """Raised when the native proc_info backend is unavailable."""


PROC_PIDLISTFDS = 1
PROC_PIDFDVNODEPATHINFO = 2
PROX_FDTYPE_VNODE = 1
PROC_PIDLISTFD_SIZE = 8
VNODEPATHINFO_SIZE = 1200
VNODEPATHINFO_PATH_OFFSET = 176
MAXPATHLEN = 1024
PROC_ROOT = Path("/proc")
LINUX_DELETED_SUFFIX = " (deleted)"


class _ProcFdInfo(ctypes.Structure):
    _fields_ = [
        ("proc_fd", ctypes.c_int32),
        ("proc_fdtype", ctypes.c_uint32),
    ]


@lru_cache(maxsize=1)
def _libproc() -> ctypes.CDLL:
    if sys.platform != "darwin":
        raise ProcInfoUnavailable("proc_pidinfo is only available on Darwin")
    try:
        libproc = ctypes.CDLL("libproc.dylib")
    except OSError as exc:
        raise ProcInfoUnavailable(str(exc)) from exc
    libproc.proc_pidinfo.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint64,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    libproc.proc_pidinfo.restype = ctypes.c_int
    libproc.proc_pidfdinfo.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    libproc.proc_pidfdinfo.restype = ctypes.c_int
    return libproc


def _extract_c_path(raw: bytes | bytearray, offset: int = VNODEPATHINFO_PATH_OFFSET) -> str:
    if offset < 0 or offset >= len(raw):
        return ""
    path_bytes = bytes(raw[offset : offset + MAXPATHLEN])
    path_bytes = path_bytes.split(b"\0", 1)[0]
    if not path_bytes:
        return ""
    try:
        return path_bytes.decode()
    except UnicodeDecodeError:
        return path_bytes.decode(errors="replace")


def _list_fds(pid: int, libproc: ctypes.CDLL) -> list[_ProcFdInfo]:
    capacity = 256
    while capacity <= 8192:
        buffer = (_ProcFdInfo * capacity)()
        size = ctypes.sizeof(buffer)
        result = libproc.proc_pidinfo(
            pid,
            PROC_PIDLISTFDS,
            0,
            ctypes.byref(buffer),
            size,
        )
        if result < 0:
            raise ProcInfoError(f"PROC_PIDLISTFDS failed for pid {pid}")
        if result == 0:
            return []
        count = result // PROC_PIDLISTFD_SIZE
        if count < capacity:
            return list(buffer[:count])
        capacity *= 2
    raise ProcInfoError(f"too many file descriptors for pid {pid}")


def _vnode_path(pid: int, fd: int, libproc: ctypes.CDLL) -> str:
    # c_ubyte is intentional: c_byte is signed and can raise ValueError when
    # converting arbitrary kernel bytes back to Python bytes.
    buffer = (ctypes.c_ubyte * VNODEPATHINFO_SIZE)()
    result = libproc.proc_pidfdinfo(
        pid,
        fd,
        PROC_PIDFDVNODEPATHINFO,
        ctypes.byref(buffer),
        VNODEPATHINFO_SIZE,
    )
    if result <= VNODEPATHINFO_PATH_OFFSET:
        return ""
    return _extract_c_path(bytearray(buffer))


def _list_open_files_darwin(pid: int) -> list[str]:
    libproc = _libproc()
    paths: list[str] = []
    seen: set[str] = set()
    for fd_info in _list_fds(pid, libproc):
        if fd_info.proc_fdtype != PROX_FDTYPE_VNODE:
            continue
        path = _vnode_path(pid, int(fd_info.proc_fd), libproc)
        if path and path.startswith("/") and path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


def _list_open_files_linux(pid: int) -> list[str]:
    fd_dir = PROC_ROOT / str(pid) / "fd"
    try:
        entries = sorted(fd_dir.iterdir(), key=lambda path: path.name)
    except FileNotFoundError:
        return []
    except PermissionError as exc:
        raise ProcInfoError(f"cannot inspect /proc fd entries for pid {pid}: {exc}") from exc
    except OSError as exc:
        raise ProcInfoError(f"cannot inspect /proc fd entries for pid {pid}: {exc}") from exc

    paths: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        try:
            target = os.readlink(entry)
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            raise ProcInfoError(f"cannot inspect fd {entry.name} for pid {pid}: {exc}") from exc
        except OSError:
            continue
        if not target.startswith("/"):
            continue
        if target.endswith(LINUX_DELETED_SUFFIX):
            continue
        if target not in seen:
            seen.add(target)
            paths.append(target)
    return paths


def list_open_files(pid: int | str) -> list[str]:
    """Return file paths currently held open by *pid*.

    Raises ``ProcInfoUnavailable`` on unsupported platforms so callers can fall
    back to portable tools such as ``lsof``.
    """

    try:
        pid_int = int(pid)
    except (TypeError, ValueError) as exc:
        raise ProcInfoError(f"invalid pid: {pid!r}") from exc
    if pid_int <= 0:
        raise ProcInfoError(f"invalid pid: {pid_int}")

    if sys.platform == "darwin":
        return _list_open_files_darwin(pid_int)
    if sys.platform.startswith("linux"):
        return _list_open_files_linux(pid_int)
    raise ProcInfoUnavailable(f"native process introspection is unavailable on {sys.platform}")
