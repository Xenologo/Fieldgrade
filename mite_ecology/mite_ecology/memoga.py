from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional
import math

from .hashutil import canonical_json, sha256_str
from .timeutil import utc_now_iso
from .kg import KnowledgeGraph

# Deterministic RNG (xorshift64*)
class DRNG:
    def __init__(self, seed_hex: str):
        seed = int(seed_hex[:16], 16) if seed_hex else 88172645463393265
        if seed == 0:
            seed = 1
        self.x = seed & ((1<<64)-1)

    def next_u64(self) -> int:
        x = self.x
        x ^= (x >> 12) & ((1<<64)-1)
        x ^= (x << 25) & ((1<<64)-1)
        x ^= (x >> 27) & ((1<<64)-1)
        self.x = x
        return (x * 2685821657736338717) & ((1<<64)-1)

    def rand(self) -> float:
        return (self.next_u64() >> 11) / float(1<<53)

    def randint(self, a: int, b: int) -> int:
        if b < a:
            a, b = b, a
        return a + int(self.rand() * ((b - a) + 1))

    def choice(self, seq):
        if not seq:
            raise ValueError("empty")
        return seq[self.randint(0, len(seq)-1)]

@dataclass
class Genome:
    genome_id: str
    context_node_id: str
    nodes: List[str]
    edges: List[int]
    params: Dict[str, Any]
    created_utc: str

def genome_from_motif(kg: KnowledgeGraph, context_node_id: str, motif_json: Dict[str, Any]) -> Genome:
    """Build a Genome from a motif payload.

    Motifs may encode edges either as:
      - integer edge ids (preferred)
      - dict edge descriptors: {src,dst,type,(attrs)}

    For dict descriptors we deterministically resolve them into edge ids via kg.upsert_edge,
    which is stable across independent runs given the same initial graph.
    """
    nodes = list(motif_json.get("nodes", []) or [])
    edges_raw = list(motif_json.get("edges", []) or [])

    resolved_edge_ids: list[int] = []
    # Resolve dict edges deterministically
    dict_edges = []
    for er in edges_raw:
        if isinstance(er, int):
            resolved_edge_ids.append(er)
        elif isinstance(er, dict):
            src = er.get("src") or er.get("source")
            dst = er.get("dst") or er.get("target")
            ety = er.get("type") or er.get("relation")
            attrs = er.get("attrs") or er.get("attrs_json") or {}
            if src is None or dst is None or ety is None:
                continue
            dict_edges.append((str(src), str(dst), str(ety), attrs))

    # Sort dict edges by stable key to guarantee deterministic insertion/lookup order
    dict_edges.sort(key=lambda t: sha256_str(canonical_json({"src": t[0], "dst": t[1], "type": t[2], "attrs": t[3]})))

    for src, dst, ety, attrs in dict_edges:
        eid = kg.upsert_edge(src, dst, ety, attrs if isinstance(attrs, dict) else {})
        resolved_edge_ids.append(int(eid))
        # Ensure endpoints are included in node set
        nodes.append(src)
        nodes.append(dst)

    # Canonicalise nodes/edges
    nodes = sorted(set(map(str, nodes)))
    resolved_edge_ids = sorted(set(map(int, resolved_edge_ids)))

    # genome params kept small + deterministic
    params = {"dropout": 0.1, "width": 128}
    base = {"context": context_node_id, "nodes": nodes, "edges": resolved_edge_ids, "params": params}
    gid = sha256_str(canonical_json(base))
    return Genome(genome_id=gid, context_node_id=context_node_id, nodes=nodes, edges=resolved_edge_ids, params=params, created_utc=utc_now_iso())

def fitness_of_genome(kg: KnowledgeGraph, g: Genome) -> Tuple[float, Dict[str, Any]]:
    # memoized
    row = kg.con.execute("SELECT fitness, eval_json FROM genome_eval WHERE genome_id=?", (g.genome_id,)).fetchone()
    if row:
        return float(row["fitness"]), json.loads(row["eval_json"])

    # Evaluate using attention weights + compactness penalty + node type coverage proxy
    score = 0.0
    if g.edges:
        qmarks=",".join(["?"]*len(g.edges))
        rows = kg.con.execute(
            f"SELECT e.id, a.score FROM edges e LEFT JOIN edge_attention a ON a.edge_id=e.id WHERE e.id IN ({qmarks})",
            tuple(g.edges),
        ).fetchall()
        for r in rows:
            if r["score"] is not None:
                score += float(r["score"])
            else:
                score += 0.01

    # compactness penalty
    penalty = 0.02 * len(g.nodes) + 0.01 * len(g.edges)

    # bonus: includes Document/Chunk/Blob types suggest "evidence"
    bonus = 0.0
    if g.nodes:
        qmarks=",".join(["?"]*len(g.nodes))
        rows = kg.con.execute(f"SELECT type FROM nodes WHERE id IN ({qmarks})", tuple(g.nodes)).fetchall()
        types = {str(r["type"]) for r in rows}
        if "Task" in types: bonus += 0.2
        if "Document" in types: bonus += 0.1
        if "Chunk" in types: bonus += 0.05

    fitness = float(score + bonus - penalty)
    eval_obj = {"score": score, "bonus": bonus, "penalty": penalty, "nodes": len(g.nodes), "edges": len(g.edges)}
    kg.con.execute(
        "INSERT OR REPLACE INTO genome_eval(genome_id, fitness, eval_json, evaluated_utc) VALUES(?,?,?,?)",
        (g.genome_id, fitness, canonical_json(eval_obj), utc_now_iso()),
    )
    kg.con.commit()
    return fitness, eval_obj

def mutate(kg: KnowledgeGraph, g: Genome, drng: DRNG, *, max_nodes: int, max_edges: int) -> Genome:
    nodes = list(g.nodes)
    edges = list(g.edges)
    # Mutate by adding/removing edges/nodes within neighborhood induced by context
    # Pull candidate edges from graph among current nodes and some neighbors
    ctx = g.context_node_id
    nb_nodes, nb_edges = kg.neighborhood(ctx, hops=2, max_nodes=400)
    nb_edge_ids = [e.id for e in nb_edges]
    if drng.rand() < 0.5 and nb_edge_ids and len(edges) < max_edges:
        # add an edge
        cand = drng.choice(nb_edge_ids)
        if cand not in edges:
            edges.append(cand)
    else:
        # remove random edge
        if edges:
            edges.pop(drng.randint(0, len(edges)-1))

    # Adjust nodes to include endpoints of selected edges
    if edges:
        qmarks=",".join(["?"]*len(edges))
        rows = kg.con.execute(f"SELECT src,dst FROM edges WHERE id IN ({qmarks})", tuple(edges)).fetchall()
        nodes_set=set(nodes)
        for r in rows:
            nodes_set.add(str(r["src"])); nodes_set.add(str(r["dst"]))
        nodes = sorted(nodes_set)[:max_nodes]

    params = dict(g.params)
    # mutate param slightly
    if drng.rand() < 0.5:
        params["dropout"] = round(min(0.6, max(0.0, float(params.get("dropout",0.1)) + (drng.rand()-0.5)*0.1)), 4)
    else:
        params["width"] = int(min(1024, max(32, int(params.get("width",128)) + (drng.randint(-32,32)))))

    base = {"context": ctx, "nodes": nodes, "edges": sorted(edges), "params": params}
    gid = sha256_str(canonical_json(base))
    return Genome(genome_id=gid, context_node_id=ctx, nodes=nodes, edges=sorted(edges), params=params, created_utc=utc_now_iso())

def crossover(g1: Genome, g2: Genome, drng: DRNG, *, max_nodes: int, max_edges: int) -> Genome:
    ctx = g1.context_node_id
    # combine a subset of edges
    e = sorted(set(g1.edges[:]) | set(g2.edges[:]))
    # sample
    keep = []
    for eid in e:
        if drng.rand() < 0.5:
            keep.append(eid)
    keep = keep[:max_edges]
    nodes = sorted(set(g1.nodes) | set(g2.nodes))[:max_nodes]
    params = {"dropout": (float(g1.params.get("dropout",0.1)) + float(g2.params.get("dropout",0.1))) / 2.0,
              "width": int((int(g1.params.get("width",128)) + int(g2.params.get("width",128))) / 2)}
    base = {"context": ctx, "nodes": nodes, "edges": keep, "params": params}
    gid = sha256_str(canonical_json(base))
    return Genome(genome_id=gid, context_node_id=ctx, nodes=nodes, edges=keep, params=params, created_utc=utc_now_iso())


def run_memoga(
    kg: KnowledgeGraph,
    *,
    context_node_id: str,
    motifs: Optional[List[Any]] = None,
    population: int = 32,
    generations: int = 12,
    seed_hex: Optional[str] = None,
    seed: Optional[str] = None,
    elite_k: Optional[int] = None,
    mutation_rate: float = 0.35,
    crossover_rate: float = 0.55,
    max_nodes: int = 128,
    max_edges: int = 256,
) -> Dict[str, Any]:
    """Deterministic memo-genetic optimisation over genomes derived from motifs.

    Backwards/forwards compatibility notes:
    - Accepts `seed_hex` (newer callers) or `seed` (older callers). If both are provided,
      `seed_hex` wins.
    - Accepts optional `motifs` list. If omitted, will fall back to the best motif in DB for the context.
    - Accepts motif items as either:
        * dict-like objects with a `score` and `nodes/edges` payload
        * `Motif` dataclass instances (from mite_ecology.motif)
    - Returns a JSON-serialisable dict summary (used by CLI + autorun tests), while persisting the
      winning genome into the DB.
    """

    # Resolve deterministic seed
    seed_final = seed_hex or seed or sha256_str(f"{context_node_id}|default_seed")

    # Elite count defaults to ~20% of population (>=1)
    elite = int(elite_k) if elite_k is not None else max(1, int(math.ceil(population * 0.2)))

    # ----- choose starting motif deterministically -----
    def _motif_to_json(m: Any) -> Dict[str, Any]:
        # Motif dataclass shape (motif_id, context_node_id, nodes, edges, score, created_utc)
        if hasattr(m, "nodes") and hasattr(m, "edges"):
            return {
                "context": getattr(m, "context_node_id", context_node_id),
                "nodes": list(getattr(m, "nodes")),
                "edges": list(getattr(m, "edges")),
                "score": float(getattr(m, "score", 0.0)),
            }
        # dict-ish
        if isinstance(m, dict):
            return {
                "context": m.get("context", context_node_id),
                "nodes": list(m.get("nodes", [])),
                "edges": list(m.get("edges", [])),
                "score": float(m.get("score", 0.0)),
            }
        # unknown -> empty motif
        return {"context": context_node_id, "nodes": [context_node_id], "edges": [], "score": 0.0}

    base_motif_json: Optional[Dict[str, Any]] = None

    if motifs:
        # Sort deterministically: score desc, then canonical payload hash asc
        norm = [_motif_to_json(m) for m in motifs]
        norm.sort(key=lambda x: (-float(x.get("score", 0.0)), sha256_str(canonical_json({k: x[k] for k in ("context", "nodes", "edges") if k in x}))))
        base_motif_json = norm[0]
    else:
        motif_row = kg.con.execute(
            "SELECT motif_json, score FROM motifs WHERE context_node_id=? ORDER BY score DESC, motif_id ASC LIMIT 1",
            (context_node_id,),
        ).fetchone()
        if motif_row:
            try:
                base_motif_json = json.loads(motif_row["motif_json"])
                # if stored motif lacks score field, add it for completeness
                if isinstance(base_motif_json, dict) and "score" not in base_motif_json:
                    base_motif_json["score"] = float(motif_row["score"])
            except Exception:
                base_motif_json = None

    if base_motif_json:
        base = genome_from_motif(kg, context_node_id, base_motif_json)
    else:
        base = Genome(
            genome_id=sha256_str(context_node_id),
            context_node_id=context_node_id,
            nodes=[context_node_id],
            edges=[],
            params={"dropout": 0.1, "width": 128},
            created_utc=utc_now_iso(),
        )

    drng = DRNG(seed_hex=seed_final)

    # ----- initialise population deterministically -----
    pop: List[Genome] = [base]
    while len(pop) < int(population):
        pop.append(mutate(kg, pop[-1], drng, max_nodes=max_nodes, max_edges=max_edges))

    best = pop[0]
    best_fit, best_ev = fitness_of_genome(kg, best)

    for _gen in range(int(generations)):
        scored: List[Tuple[float, Genome]] = []
        for g in pop:
            fit, _ev = fitness_of_genome(kg, g)
            scored.append((fit, g))
        scored.sort(key=lambda x: (x[0], x[1].genome_id), reverse=True)

        elites = [g for _, g in scored[: max(1, elite)]]

        # update best
        if scored and scored[0][0] > best_fit:
            best_fit = float(scored[0][0])
            best = scored[0][1]
            best_fit, best_ev = fitness_of_genome(kg, best)

        new_pop = elites[:]
        while len(new_pop) < int(population):
            if drng.rand() < float(crossover_rate) and len(elites) >= 2:
                p1 = drng.choice(elites)
                p2 = drng.choice(elites)
                child = crossover(p1, p2, drng, max_nodes=max_nodes, max_edges=max_edges)
            else:
                child = drng.choice(elites)

            if drng.rand() < float(mutation_rate):
                child = mutate(kg, child, drng, max_nodes=max_nodes, max_edges=max_edges)
            new_pop.append(child)

        pop = new_pop

    # Persist best genome
    gobj = {"context": best.context_node_id, "nodes": best.nodes, "edges": best.edges, "params": best.params}
    kg.con.execute(
        "INSERT OR REPLACE INTO genomes(genome_id, context_node_id, genome_json, created_utc) VALUES(?,?,?,?)",
        (best.genome_id, best.context_node_id, canonical_json(gobj), utc_now_iso()),
    )
    kg.con.commit()

    # Ensure we have eval cached and captured in response
    best_fit, best_ev = fitness_of_genome(kg, best)

    return {
        "context_node_id": context_node_id,
        "seed_hex": seed_final,
        "population": int(population),
        "generations": int(generations),
        "elite_k": int(elite),
        "mutation_rate": float(mutation_rate),
        "crossover_rate": float(crossover_rate),
        "max_nodes": int(max_nodes),
        "max_edges": int(max_edges),
        "best_genome_id": best.genome_id,
        "best_fitness": float(best_fit),
        "best_eval": best_ev,
        "best_genome": gobj,
    }
