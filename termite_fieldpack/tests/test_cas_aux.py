from __future__ import annotations

from pathlib import Path

from termite.cas import CAS


def test_cas_aux_roundtrip(tmp_path: Path):
    cas = CAS(tmp_path / "cas")
    cas.init()
    data = b"hello\n"
    sha = cas.put_aux(data)
    p = cas.get_aux_path(sha)
    assert p.exists()
    assert p.read_bytes() == data
