from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import requests
from jsonschema import Draft202012Validator

from .hashutil import canonical_json, sha256_str
from .timeutil import utc_now_iso
from .kg import KnowledgeGraph, Node, Edge
from .delta import apply_delta_lines
from .gnn import message_passing_embeddings
from .gat import compute_edge_attention


# -----------------------------
# Config structures (read from ecology.yaml)
# -----------------------------

@dataclass(frozen=True)
class LLMContextCfg:
    hops: int = 2
    max_nodes: int = 120
    max_edges: int = 220
    top_attention_edges: int = 48

@dataclass(frozen=True)
class LLMConfig:
    endpoint_source: str
    endpoint_id: Optional[str]
    termite_toolchain_id: Optional[str]
    base_url: str
    api_key_env: str
    model: str
    temperature: float
    timeout_s: int
    max_tokens: int
    require_prompt_hash_echo: bool
    schemas_dir: Path
    context: LLMContextCfg
    prompts: Dict[str, str]


# -----------------------------
# Scope rules
# -----------------------------

def parse_scope_rule(rule: str) -> Dict[str, Any]:
    """
    Parse a simple semicolon-separated rule string like:
      "root=task:abc;hops=2;max_nodes=120;top_attention_edges=48"
    Also accepts the short form:
      "task:abc" -> root=task:abc
    """
    s = (rule or "").strip()
    out: Dict[str, Any] = {}
    if not s:
        return out
    if ";" not in s and "=" not in s:
        out["root"] = s
        return out
    parts = [p.strip() for p in s.split(";") if p.strip()]
    for p in parts:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k in {"hops","max_nodes","max_edges","top_attention_edges"}:
            try:
                out[k] = int(v)
            except Exception:
                pass
        else:
            out[k] = v
    return out


# -----------------------------
# Schema loading / validation
# -----------------------------

@dataclass
class Schemas:
    kg_delta_op: Draft202012Validator
    motif_spec: Draft202012Validator
    neuroarch_dsl: Draft202012Validator

def _load_schema_validator(path: Path) -> Draft202012Validator:
    obj = json.loads(path.read_text(encoding="utf-8"))
    return Draft202012Validator(obj)

def load_schemas(schemas_dir: Path) -> Schemas:
    sd = schemas_dir.resolve()
    return Schemas(
        kg_delta_op=_load_schema_validator(sd / "kg_delta.json"),
        motif_spec=_load_schema_validator(sd / "motif_spec.json"),
        neuroarch_dsl=_load_schema_validator(sd / "neuroarch_dsl.json"),
    )


# -----------------------------
# LLM calling (OpenAI-compatible endpoint)
# -----------------------------

@dataclass
class LLMEndpoint:
    base_url: str
    api_key: Optional[str]
    timeout_s: int = 120

    def chat(self, messages: List[Dict[str, str]], *, model: str, temperature: float, max_tokens: int) -> str:
        url = self.base_url.rstrip("/") + "/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": model,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "messages": messages,
        }
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=self.timeout_s)
        r.raise_for_status()
        obj = r.json()
        return obj["choices"][0]["message"]["content"]


# -----------------------------
# Context pack construction
# -----------------------------

def _edge_row_by_id(kg: KnowledgeGraph, edge_id: int) -> Optional[Edge]:
    r = kg.con.execute("SELECT id,edge_key,src,dst,type,attrs_json FROM edges WHERE id=?", (edge_id,)).fetchone()
    if not r:
        return None
    return Edge(
        id=int(r["id"]),
        edge_key=str(r["edge_key"]),
        src=str(r["src"]),
        dst=str(r["dst"]),
        type=str(r["type"]),
        attrs=json.loads(r["attrs_json"]),
    )

def _sort_nodes(nodes: List[Node]) -> List[Node]:
    return sorted(nodes, key=lambda n: (sha256_str(n.id), n.id))

def _sort_edges(edges: List[Edge]) -> List[Edge]:
    return sorted(edges, key=lambda e: (e.edge_key, sha256_str(e.edge_key)))

def build_context_pack(
    kg: KnowledgeGraph,
    root_id: str,
    *,
    hops: int,
    max_nodes: int,
    max_edges: int,
    top_attention_edges: int,
    include_attention: bool = True,
) -> Dict[str, Any]:
    nodes, edges = kg.neighborhood(root_id, hops=hops, max_nodes=max_nodes)

    # attention-guided selection if available
    att_edges: List[Tuple[int, float]] = []
    if include_attention:
        try:
            att_edges = kg.list_attention(root_id, limit=top_attention_edges)
        except Exception:
            att_edges = []

    # If no attention yet, compute it deterministically (no training) for the neighborhood
    if include_attention and not att_edges and nodes and edges:
        emb = message_passing_embeddings(nodes, edges, feature_dim=32, hops=hops)
        # compute attention for all edges in the neighborhood
        scores = compute_edge_attention(nodes, edges, emb, alpha=0.2)
        # store + collect
        for e in edges:
            sc = float(scores.get(e.id, 0.0))
            kg.set_edge_attention(e.id, sc, root_id)
        att_edges = kg.list_attention(root_id, limit=top_attention_edges)

    # Select edges: top attention edges first, then fill by stable order
    chosen_edge_ids = []
    seen_ids = set()
    for eid, _sc in att_edges:
        if eid not in seen_ids:
            chosen_edge_ids.append(eid)
            seen_ids.add(eid)

    # fill
    if len(chosen_edge_ids) < min(max_edges, len(edges)):
        # stable sort by edge_key
        for e in _sort_edges(edges):
            if e.id not in seen_ids:
                chosen_edge_ids.append(e.id)
                seen_ids.add(e.id)
            if len(chosen_edge_ids) >= max_edges:
                break

    chosen_edges: List[Edge] = []
    chosen_nodes = {root_id}
    for eid in chosen_edge_ids[:max_edges]:
        er = _edge_row_by_id(kg, eid)
        if er is None:
            continue
        chosen_edges.append(er)
        chosen_nodes.add(er.src)
        chosen_nodes.add(er.dst)

    # Ensure nodes include all incident nodes, capped deterministically
    node_rows = []
    for nid in chosen_nodes:
        r = kg.con.execute("SELECT id,type,attrs_json FROM nodes WHERE id=?", (nid,)).fetchone()
        if r:
            node_rows.append(Node(id=str(r["id"]), type=str(r["type"]), attrs=json.loads(r["attrs_json"])))

    # If too many nodes, deterministically trim by hash order
    node_rows = _sort_nodes(node_rows)
    if len(node_rows) > max_nodes:
        node_rows = node_rows[:max_nodes]

    # Filter edges to those whose endpoints survived
    node_set = {n.id for n in node_rows}
    chosen_edges = [e for e in _sort_edges(chosen_edges) if e.src in node_set and e.dst in node_set][:max_edges]

    pack = {
        "context_pack_version": "1.0",
        "root": root_id,
        "hops": int(hops),
        "nodes": [
            {"id": n.id, "type": n.type, "attrs": n.attrs}
            for n in node_rows
        ],
        "edges": [
            {"id": e.id, "edge_key": e.edge_key, "src": e.src, "dst": e.dst, "type": e.type, "attrs": e.attrs}
            for e in chosen_edges
        ],
    }

    if include_attention and att_edges:
        pack["attention_ranked_edges"] = [
            {"edge_id": int(eid), "score": float(sc)}
            for eid, sc in att_edges
        ]

    # stable hashes
    pack_canon = canonical_json(pack)
    pack["context_pack_hash"] = sha256_str(pack_canon)
    return pack


# -----------------------------
# LLM wrapper format + parsing
# -----------------------------

@dataclass
class LLMResult:
    response_kind: str
    prompt_hash_echo: Optional[str]
    content: Any
    raw_text: str

ALLOWED_KINDS = {"kg_delta.jsonl", "motif_spec.json", "neuroarch_dsl.json"}

def parse_llm_wrapper(text: str) -> LLMResult:
    raw = text.strip()
    obj = json.loads(raw)
    kind = str(obj.get("response_kind", "")).strip()
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"Invalid response_kind: {kind!r}")
    return LLMResult(
        response_kind=kind,
        prompt_hash_echo=(str(obj.get("prompt_hash")) if obj.get("prompt_hash") is not None else None),
        content=obj.get("content"),
        raw_text=raw,
    )


# -----------------------------
# Provenance-linked delta logging
# -----------------------------

def _latest_delta_hash(kg: KnowledgeGraph) -> Optional[str]:
    r = kg.con.execute("SELECT delta_hash FROM kg_deltas ORDER BY id DESC LIMIT 1").fetchone()
    return None if not r else str(r["delta_hash"])

def _hash_delta(prev_hash: Optional[str], kind: str, payload_text: str) -> str:
    return sha256_str((prev_hash or "") + "|" + kind + "|" + payload_text)

def append_kg_delta(
    kg: KnowledgeGraph,
    *,
    source: str,
    context_node_id: Optional[str],
    delta_kind: str,
    delta_payload_text: str,
) -> str:
    prev = _latest_delta_hash(kg)
    ts = utc_now_iso()
    dh = _hash_delta(prev, delta_kind, delta_payload_text)
    chain_hash = sha256_str((prev or "") + "|" + dh)
    kg.con.execute(
        "INSERT INTO kg_deltas(ts_utc,source,context_node_id,delta_kind,delta_payload,prev_hash,delta_hash,chain_hash) VALUES(?,?,?,?,?,?,?,?)",
        (ts, source, context_node_id, delta_kind, delta_payload_text, prev, dh, chain_hash),
    )
    kg.con.commit()
    return dh


# -----------------------------
# Converting motif/neuroarch to KG ops
# -----------------------------

def motif_spec_to_ops(spec: Dict[str, Any], *, prompt_hash: str, context_hash: str) -> List[Dict[str, Any]]:
    canon = canonical_json(spec)
    mid = sha256_str(canon)
    ctx = str(spec.get("context") or "")
    motif_node = f"motif:{mid}"
    ops: List[Dict[str, Any]] = []
    ops.append({"op": "ADD_NODE", "id": motif_node, "type": "MotifSpec", "attrs": {
        "source": "LLM",
        "prompt_hash": prompt_hash,
        "context_pack_hash": context_hash,
        "motif_spec": spec,
    }})
    if ctx:
        ops.append({"op": "ADD_EDGE", "src": ctx, "dst": motif_node, "type": "PROPOSED_MOTIF", "attrs": {}})
    # link included nodes
    for nid in (spec.get("nodes") or []):
        if isinstance(nid, str):
            ops.append({"op":"ADD_EDGE","src": motif_node, "dst": nid, "type":"MOTIF_INCLUDES_NODE", "attrs": {}})
    return ops

def neuroarch_to_ops(spec: Dict[str, Any], *, prompt_hash: str, context_hash: str) -> List[Dict[str, Any]]:
    canon = canonical_json(spec)
    aid = sha256_str(canon)
    ctx = str(spec.get("context_node_id") or spec.get("context") or "")
    node_id = f"neuroarch:{aid}"
    ops: List[Dict[str, Any]] = []
    ops.append({"op":"ADD_NODE","id": node_id, "type":"NeuroArch", "attrs": {
        "source":"LLM",
        "prompt_hash": prompt_hash,
        "context_pack_hash": context_hash,
        "neuroarch_dsl": spec,
    }})
    if ctx:
        ops.append({"op":"ADD_EDGE","src": ctx, "dst": node_id, "type":"PROPOSED_NEUROARCH", "attrs": {}})
    return ops


# -----------------------------
# Main sync / propose APIs
# -----------------------------

def _ensure_task_exists(kg: KnowledgeGraph, task_id: str) -> None:
    r = kg.con.execute("SELECT 1 FROM nodes WHERE id=?", (task_id,)).fetchone()
    if not r:
        raise RuntimeError(f"Task/root node not found: {task_id}")


def _get_termite_llm_status(llm_raw: Dict[str, Any], base_dir: Path) -> Dict[str, Any]:
    """
    Ask Termite for the active LLM endpoint identity.
    Resolution order:
      1) read termite runtime state JSON if provided (llm.termite.state_path)
      2) run termite CLI: <cmd> --config <path> llm status --json
    """
    t = llm_raw.get("termite") or {}

    state_path = t.get("state_path")
    if state_path:
        sp = Path(str(state_path))
        if not sp.is_absolute():
            sp = (base_dir / sp).resolve()
        if sp.exists():
            return json.loads(sp.read_text(encoding="utf-8"))

    cmd = str(t.get("cmd") or "termite")
    cfg_path = t.get("config_path")
    argv: List[str] = [cmd]
    if cfg_path:
        cp = Path(str(cfg_path))
        if not cp.is_absolute():
            cp = (base_dir / cp).resolve()
        argv += ["--config", str(cp)]
    argv += ["llm", "status", "--json"]

    timeout_raw = (os.environ.get("MITE_ECOLOGY_LLM_STATUS_TIMEOUT_S") or "10").strip()
    try:
        timeout_s = float(timeout_raw)
    except Exception:
        timeout_s = 10.0
    if timeout_s <= 0:
        timeout_s = None
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "timeout_s": timeout_s, "argv": argv}
    if r.stdout.strip():
        try:
            return json.loads(r.stdout)
        except Exception:
            pass
    r.check_returncode()
    return json.loads(r.stdout)


def _llm_cfg_from_raw(raw: Dict[str, Any], base_dir: Path) -> LLMConfig:
    llm = raw.get("llm") or {}
    ctx = llm.get("context") or {}
    prompts = llm.get("prompts") or {}

    sd = Path(llm.get("schemas_dir") or "../schemas")
    if not sd.is_absolute():
        sd = (base_dir / sd).resolve()

    endpoint_source = str(llm.get("endpoint_source") or "direct").strip().lower()
    endpoint_id: Optional[str] = None
    termite_toolchain_id: Optional[str] = None

    base_url = str(llm.get("base_url") or "http://127.0.0.1:8000")
    model = str(llm.get("model") or "qwen2.5-coder-0.5b-instruct")

    if endpoint_source == "termite":
        st = _get_termite_llm_status(llm, base_dir)
        # termite runtime state uses base_url; config uses endpoint_base_url
        base_url = str(st.get("base_url") or st.get("endpoint_base_url") or base_url)
        model = str(st.get("model") or model)
        if st.get("endpoint_id") is not None:
            endpoint_id = str(st.get("endpoint_id"))
        if st.get("toolchain_id") is not None:
            termite_toolchain_id = str(st.get("toolchain_id"))
        require_running = bool((llm.get("termite") or {}).get("require_running", True))
        if require_running and not bool(st.get("running", False)):
            raise RuntimeError("Termite reports LLM is not running. Start it with: termite llm start")

    return LLMConfig(
        endpoint_source=endpoint_source,
        endpoint_id=endpoint_id,
        termite_toolchain_id=termite_toolchain_id,
        base_url=base_url,
        api_key_env=str(llm.get("api_key_env") or "OPENAI_API_KEY"),
        model=model,
        temperature=float(llm.get("temperature") if llm.get("temperature") is not None else 0.0),
        timeout_s=int(llm.get("timeout_s") or 120),
        max_tokens=int(llm.get("max_tokens") or 1200),
        require_prompt_hash_echo=bool(llm.get("require_prompt_hash_echo", True)),
        schemas_dir=sd,
        context=LLMContextCfg(
            hops=int(ctx.get("hops") or 2),
            max_nodes=int(ctx.get("max_nodes") or 120),
            max_edges=int(ctx.get("max_edges") or 220),
            top_attention_edges=int(ctx.get("top_attention_edges") or 48),
        ),
        prompts={k: str(v) for k, v in prompts.items()},
    )


def _hash_response_text(s: str) -> str:
    return sha256_str(s.strip())

def call_llm_and_validate(
    kg: KnowledgeGraph,
    *,
    cfg_raw: Dict[str, Any],
    cfg_base_dir: Path,
    task_id: str,
    scope_rule: str,
    prompt_template: str,
    desired_kind: Optional[str],
) -> Tuple[LLMResult, str, str]:
    """
    Returns (parsed_result, prompt_hash, context_hash)
    """
    llm_cfg = _llm_cfg_from_raw(cfg_raw, cfg_base_dir)
    schemas = load_schemas(llm_cfg.schemas_dir)

    # derive effective context parameters from scope_rule overrides
    rule = parse_scope_rule(scope_rule)
    root = str(rule.get("root") or task_id)

    hops = int(rule.get("hops") or llm_cfg.context.hops)
    max_nodes = int(rule.get("max_nodes") or llm_cfg.context.max_nodes)
    max_edges = int(rule.get("max_edges") or llm_cfg.context.max_edges)
    top_att = int(rule.get("top_attention_edges") or llm_cfg.context.top_attention_edges)

    _ensure_task_exists(kg, root)

    context_pack = build_context_pack(
        kg,
        root,
        hops=hops,
        max_nodes=max_nodes,
        max_edges=max_edges,
        top_attention_edges=top_att,
        include_attention=True,
    )
    context_hash = str(context_pack["context_pack_hash"])

    # Build deterministic prompt
    prompt_obj = {
        "policy": "mite_ecology_llm_sync_v1",
        "desired_kind": desired_kind,
        "root": root,
        "scope_rule": scope_rule,
        "context_pack": context_pack,
    }
    prompt_user = prompt_template.strip() + "\n\n" + canonical_json(prompt_obj) + "\n"
    prompt_hash = sha256_str(prompt_user)

    # Compose messages: system + user, and require prompt_hash echo
    system_prompt = (llm_cfg.prompts.get("sync") or "").strip()
    if not system_prompt:
        system_prompt = "Return only JSON. See user instructions."

    # Include prompt_hash in the prompt to force echo binding
    user_with_hash = f"prompt_hash={prompt_hash}\n" + prompt_user

    endpoint = LLMEndpoint(
        base_url=llm_cfg.base_url,
        api_key=os.getenv(llm_cfg.api_key_env),
        timeout_s=llm_cfg.timeout_s,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_with_hash},
    ]

    req_json = canonical_json({
        "endpoint_source": llm_cfg.endpoint_source,
        "endpoint_id": llm_cfg.endpoint_id,
        "termite_toolchain_id": llm_cfg.termite_toolchain_id,
        "base_url": llm_cfg.base_url,
        "model": llm_cfg.model,
        "temperature": llm_cfg.temperature,
        "max_tokens": llm_cfg.max_tokens,
        "messages": messages,
    })

    # call
    raw_text = endpoint.chat(
        messages,
        model=llm_cfg.model,
        temperature=llm_cfg.temperature,
        max_tokens=llm_cfg.max_tokens,
    )

    resp_hash = _hash_response_text(raw_text)
    parsed_kind = None
    parsed_payload = None
    parsed_hash = None
    ok = 0
    err = None

    try:
        res = parse_llm_wrapper(raw_text)
        parsed_kind = res.response_kind
        if llm_cfg.require_prompt_hash_echo and (res.prompt_hash_echo != prompt_hash):
            raise ValueError(f"prompt_hash echo mismatch: got {res.prompt_hash_echo!r}, expected {prompt_hash!r}")

        if desired_kind and res.response_kind != desired_kind:
            raise ValueError(f"LLM returned {res.response_kind}, expected {desired_kind}")

        # validate
        if res.response_kind == "kg_delta.jsonl":
            if not isinstance(res.content, str):
                raise ValueError("kg_delta.jsonl content must be a string (JSONL)")
            lines = [ln for ln in res.content.splitlines() if ln.strip()]
            for ln in lines:
                obj = json.loads(ln)
                schemas.kg_delta_op.validate(obj)
            parsed_payload = res.content
            parsed_hash = sha256_str(res.content.strip())
            ok = 1

        elif res.response_kind == "motif_spec.json":
            if not isinstance(res.content, dict):
                raise ValueError("motif_spec.json content must be an object")
            schemas.motif_spec.validate(res.content)
            parsed_payload = canonical_json(res.content)
            parsed_hash = sha256_str(parsed_payload)
            ok = 1

        elif res.response_kind == "neuroarch_dsl.json":
            if not isinstance(res.content, dict):
                raise ValueError("neuroarch_dsl.json content must be an object")
            schemas.neuroarch_dsl.validate(res.content)
            parsed_payload = canonical_json(res.content)
            parsed_hash = sha256_str(parsed_payload)
            ok = 1

        else:
            raise ValueError(f"Unsupported kind: {res.response_kind}")

        # store llm call record
        kg.con.execute(
            "INSERT INTO llm_calls(ts_utc,context_node_id,scope_rule,endpoint_base_url,model,temperature,prompt_hash,context_hash,request_json,response_text,response_hash,parsed_kind,parsed_payload,parsed_hash,validation_ok,error) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (utc_now_iso(), root, scope_rule, llm_cfg.base_url, llm_cfg.model, float(llm_cfg.temperature),
             prompt_hash, context_hash, req_json, raw_text, resp_hash, parsed_kind, parsed_payload, parsed_hash, ok, None),
        )
        kg.con.commit()

        return res, prompt_hash, context_hash

    except Exception as e:
        err = str(e)
        kg.con.execute(
            "INSERT INTO llm_calls(ts_utc,context_node_id,scope_rule,endpoint_base_url,model,temperature,prompt_hash,context_hash,request_json,response_text,response_hash,parsed_kind,parsed_payload,parsed_hash,validation_ok,error) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (utc_now_iso(), task_id, scope_rule, llm_cfg.base_url if 'llm_cfg' in locals() else "unknown",
             llm_cfg.model if 'llm_cfg' in locals() else "unknown",
             float(llm_cfg.temperature) if 'llm_cfg' in locals() else 0.0,
             prompt_hash if 'prompt_hash' in locals() else "unknown",
             context_hash if 'context_hash' in locals() else "unknown",
             req_json if 'req_json' in locals() else "{}",
             raw_text if 'raw_text' in locals() else "",
             resp_hash if 'resp_hash' in locals() else "",
             parsed_kind, parsed_payload, parsed_hash, 0, err),
        )
        kg.con.commit()
        raise


def apply_llm_result_to_kg(
    kg: KnowledgeGraph,
    *,
    res: LLMResult,
    prompt_hash: str,
    context_hash: str,
) -> int:
    """
    Applies the validated LLM output to the KG and records a provenance-linked kg_deltas row.
    Returns number of ops applied (for kg_delta) or ops generated (for motif/neuroarch).
    """
    if res.response_kind == "kg_delta.jsonl":
        assert isinstance(res.content, str)
        payload = res.content.strip() + ("\n" if res.content and not res.content.endswith("\n") else "")
        append_kg_delta(kg, source="LLM", context_node_id=None, delta_kind="kg_delta.jsonl", delta_payload_text=payload)
        return apply_delta_lines(kg, payload.splitlines())

    if res.response_kind == "motif_spec.json":
        assert isinstance(res.content, dict)
        # enrich with required context binding if missing
        if "context" not in res.content:
            # best effort: use root in pack; but pack isn't passed; leave as is
            pass
        # log the spec itself as delta payload
        payload = canonical_json(res.content)
        append_kg_delta(kg, source="LLM", context_node_id=str(res.content.get("context") or ""), delta_kind="motif_spec.json", delta_payload_text=payload)
        ops = motif_spec_to_ops(res.content, prompt_hash=prompt_hash, context_hash=context_hash)
        op_lines = [canonical_json(o) for o in ops]
        return apply_delta_lines(kg, op_lines)

    if res.response_kind == "neuroarch_dsl.json":
        assert isinstance(res.content, dict)
        payload = canonical_json(res.content)
        append_kg_delta(kg, source="LLM", context_node_id=str(res.content.get("context_node_id") or ""), delta_kind="neuroarch_dsl.json", delta_payload_text=payload)
        ops = neuroarch_to_ops(res.content, prompt_hash=prompt_hash, context_hash=context_hash)
        op_lines = [canonical_json(o) for o in ops]
        return apply_delta_lines(kg, op_lines)

    raise ValueError(f"Unsupported kind: {res.response_kind}")


# Convenience wrappers for CLI

def llm_sync(kg: KnowledgeGraph, *, cfg_raw: Dict[str, Any], cfg_base_dir: Path, task_id: str, scope_rule: str = "") -> int:
    prompt_template = ((cfg_raw.get("llm") or {}).get("prompts") or {}).get("sync") or ""
    if not prompt_template.strip():
        prompt_template = "Generate a valid artifact as instructed."
    res, ph, ch = call_llm_and_validate(
        kg,
        cfg_raw=cfg_raw,
        cfg_base_dir=cfg_base_dir,
        task_id=task_id,
        scope_rule=scope_rule,
        prompt_template=prompt_template,
        desired_kind=None,
    )
    return apply_llm_result_to_kg(kg, res=res, prompt_hash=ph, context_hash=ch)

def llm_propose_motif(kg: KnowledgeGraph, *, cfg_raw: Dict[str, Any], cfg_base_dir: Path, task_id: str, scope_rule: str = "") -> int:
    prompts = ((cfg_raw.get("llm") or {}).get("prompts") or {})
    prompt_template = prompts.get("propose_motif") or prompts.get("sync") or ""
    res, ph, ch = call_llm_and_validate(
        kg,
        cfg_raw=cfg_raw,
        cfg_base_dir=cfg_base_dir,
        task_id=task_id,
        scope_rule=scope_rule,
        prompt_template=prompt_template,
        desired_kind="motif_spec.json",
    )
    return apply_llm_result_to_kg(kg, res=res, prompt_hash=ph, context_hash=ch)

def llm_propose_delta(kg: KnowledgeGraph, *, cfg_raw: Dict[str, Any], cfg_base_dir: Path, task_id: str, scope_rule: str) -> int:
    prompts = ((cfg_raw.get("llm") or {}).get("prompts") or {})
    prompt_template = prompts.get("propose_delta") or prompts.get("sync") or ""
    res, ph, ch = call_llm_and_validate(
        kg,
        cfg_raw=cfg_raw,
        cfg_base_dir=cfg_base_dir,
        task_id=task_id,
        scope_rule=scope_rule,
        prompt_template=prompt_template,
        desired_kind="kg_delta.jsonl",
    )
    return apply_llm_result_to_kg(kg, res=res, prompt_hash=ph, context_hash=ch)
