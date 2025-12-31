import tempfile, json
from pathlib import Path
from mite_ecology.db import connect, init_db
from mite_ecology.kg import KnowledgeGraph
from mite_ecology.gnn import message_passing_embeddings
from mite_ecology.gat import compute_edge_attention

def test_deterministic_embeddings_and_attention():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        con = connect(td/"kg.sqlite")
        try:
            schema = Path(__file__).resolve().parents[1]/"sql"/"schema.sql"
            init_db(con, schema)
            kg = KnowledgeGraph(con)
            kg.upsert_node("a","Task",{"name":"A"})
            kg.upsert_node("b","Thing",{"name":"B"})
            kg.upsert_node("c","Thing",{"name":"C"})
            e1 = kg.upsert_edge("a","b","REL",{})
            e2 = kg.upsert_edge("a","c","REL",{})
            nodes, edges = kg.neighborhood("a", hops=1)
            emb1 = message_passing_embeddings(nodes, edges, feature_dim=16, hops=2)
            emb2 = message_passing_embeddings(nodes, edges, feature_dim=16, hops=2)
            assert json.dumps(emb1, sort_keys=True) == json.dumps(emb2, sort_keys=True)
            att1 = compute_edge_attention(nodes, edges, emb1, context_node_id="a", alpha=0.2)
            att2 = compute_edge_attention(nodes, edges, emb2, context_node_id="a", alpha=0.2)
            assert json.dumps(att1, sort_keys=True) == json.dumps(att2, sort_keys=True)
        finally:
            con.close()
