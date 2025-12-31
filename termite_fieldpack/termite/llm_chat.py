from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from .cas import CAS
from .provenance import canonical_json, hash_str, utc_now_iso
from .config import TermiteConfig

def _hash_chain(prev_hash: Optional[str], payload: str) -> str:
    return hash_str((prev_hash or "") + "|" + payload)

def _latest_call_hash(con) -> Optional[str]:
    row = con.execute("SELECT call_hash FROM llm_calls ORDER BY id DESC LIMIT 1").fetchone()
    return None if row is None else str(row["call_hash"])

def chat(
    cfg: TermiteConfig,
    prompt: str,
    *,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    store: bool = True,
) -> Dict[str, Any]:
    """Call OpenAI-compatible LLM endpoint configured in termite.yaml (or active endpoint state).
    Strictly audited when store=True.
    """
    llm = (cfg.raw.get('llm') or {})
    base_url = str(llm.get('endpoint_base_url') or llm.get('base_url') or 'http://127.0.0.1:8000').rstrip("/")
    model = str(llm.get('model') or 'qwen2.5-coder-0.5b-instruct')
    temp = float(float(llm.get('temperature', 0.0)) if temperature is None else temperature)
    mtok = int(int(llm.get('max_tokens', 512)) if max_tokens is None else max_tokens)

    payload = {
        "model": model,
        "temperature": temp,
        "max_tokens": mtok,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get(str(llm.get('api_key_env','OPENAI_API_KEY')), '')
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    r = requests.post(f"{base_url}/v1/chat/completions", headers=headers, data=canonical_json(payload), timeout=int(llm.get('timeout_s', 30)))
    r.raise_for_status()
    data = r.json()

    # Extract best-effort assistant content
    content = ""
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        content = json.dumps(data, sort_keys=True)

    if not store:
        return {"endpoint_base_url": base_url, "model": model, "temperature": temp, "response": data, "content": content}

    # store request/response in CAS aux + db
    cas = CAS(cfg.cas_root); cas.init()
    con = cfg.db_con()
    ts = utc_now_iso()

    prompt_hash = hash_str(prompt)
    req_sha = cas.put_aux((canonical_json(payload) + "\n").encode("utf-8"))
    resp_bytes = (canonical_json(data) + "\n").encode("utf-8")
    resp_sha = cas.put_aux(resp_bytes)
    resp_hash = hash_str(resp_bytes.decode("utf-8"))

    prev = _latest_call_hash(con)
    chain_payload = canonical_json({
        "ts_utc": ts,
        "endpoint_base_url": base_url,
        "model": model,
        "temperature": temp,
        "prompt_hash": prompt_hash,
        "request_aux_sha256": req_sha,
        "response_aux_sha256": resp_sha,
        "response_hash": resp_hash,
        "prev_hash": prev,
    })
    call_hash = _hash_chain(prev, chain_payload)

    con.execute(
        "INSERT INTO llm_calls(ts_utc,endpoint_base_url,model,temperature,prompt_hash,request_aux_sha256,response_aux_sha256,response_hash,prev_hash,call_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (ts, base_url, model, temp, prompt_hash, req_sha, resp_sha, resp_hash, prev, call_hash),
    )
    # provenance event
    from .provenance import Provenance
    prov = Provenance(cfg.toolchain_id)
    prov.emit(con, "LLM_CHAT", {
        "endpoint_base_url": base_url,
        "model": model,
        "temperature": temp,
        "prompt_hash": prompt_hash,
        "request_aux_sha256": req_sha,
        "response_aux_sha256": resp_sha,
        "call_hash": call_hash,
    })
    con.commit()
    return {"endpoint_base_url": base_url, "model": model, "temperature": temp, "prompt_hash": prompt_hash, "call_hash": call_hash, "content": content, "response": data}
