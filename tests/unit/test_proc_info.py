import pytest

from hive import proc_info


def test_extract_c_path_uses_vnode_path_offset_176():
    raw = bytearray(proc_info.VNODEPATHINFO_SIZE)
    path = b"/tmp/session.jsonl"
    raw[proc_info.VNODEPATHINFO_PATH_OFFSET : proc_info.VNODEPATHINFO_PATH_OFFSET + len(path)] = path

    assert proc_info._extract_c_path(raw) == "/tmp/session.jsonl"


def test_list_open_files_linux_provider_reads_proc_fd_links(monkeypatch, tmp_path):
    proc_info._libproc.cache_clear()
    proc_root = tmp_path / "proc"
    fd_dir = proc_root / "123" / "fd"
    fd_dir.mkdir(parents=True)
    (fd_dir / "0").symlink_to("/tmp/session.jsonl")
    (fd_dir / "1").symlink_to("socket:[1234]")
    (fd_dir / "2").symlink_to("/tmp/session.jsonl")
    (fd_dir / "3").symlink_to("/tmp/deleted.jsonl (deleted)")
    (fd_dir / "4").symlink_to("/tmp/other.log")

    monkeypatch.setattr(proc_info.sys, "platform", "linux")
    monkeypatch.setattr(proc_info, "PROC_ROOT", proc_root)

    assert proc_info.list_open_files(123) == ["/tmp/session.jsonl", "/tmp/other.log"]

    proc_info._libproc.cache_clear()


def test_list_open_files_linux_provider_tolerates_missing_process(monkeypatch, tmp_path):
    proc_info._libproc.cache_clear()
    monkeypatch.setattr(proc_info.sys, "platform", "linux")
    monkeypatch.setattr(proc_info, "PROC_ROOT", tmp_path / "proc")

    assert proc_info.list_open_files(123) == []

    proc_info._libproc.cache_clear()


def test_list_open_files_reports_unavailable_on_unsupported_platform(monkeypatch):
    proc_info._libproc.cache_clear()
    monkeypatch.setattr(proc_info.sys, "platform", "freebsd")

    with pytest.raises(proc_info.ProcInfoUnavailable):
        proc_info.list_open_files(123)

    proc_info._libproc.cache_clear()
