import pytest

from hive import proc_info


def test_extract_c_path_uses_vnode_path_offset_176():
    raw = bytearray(proc_info.VNODEPATHINFO_SIZE)
    path = b"/tmp/session.jsonl"
    raw[proc_info.VNODEPATHINFO_PATH_OFFSET : proc_info.VNODEPATHINFO_PATH_OFFSET + len(path)] = path

    assert proc_info._extract_c_path(raw) == "/tmp/session.jsonl"


def test_list_open_files_reports_unavailable_off_darwin(monkeypatch):
    proc_info._libproc.cache_clear()
    monkeypatch.setattr(proc_info.sys, "platform", "linux")

    with pytest.raises(proc_info.ProcInfoUnavailable):
        proc_info.list_open_files(123)

    proc_info._libproc.cache_clear()
