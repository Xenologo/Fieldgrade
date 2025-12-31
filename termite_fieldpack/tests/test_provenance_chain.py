import tempfile
from pathlib import Path
from termite.db import connect, init_db
from termite.provenance import Provenance, verify_chain
from termite.cas import CAS

def test_provenance_chain_ok():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        con = connect(td/"termite.sqlite")
        try:
            schema = Path(__file__).resolve().parents[1]/"sql"/"schema.sql"
            init_db(con, schema)
            prov = Provenance("TEST_TOOLCHAIN")
            prov.append_event(con, "E1", {"a":1})
            prov.append_event(con, "E2", {"b":2})
            assert verify_chain(con) is True
        finally:
            con.close()
