#!/usr/bin/env python3
"""COIL/HITT/FIELDGRADE local stack sandbox v0.3.

Demonstration only. Do not use real child data, real biometrics, genetic data,
or production platform decisions.
"""
from __future__ import annotations

import argparse, base64, copy, hashlib, hmac, json, os, sys, tempfile, time, uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

CAPABILITY_BANDS: Dict[str, Dict[str, Any]] = {
    "COIL-C0": {"title":"Child Creative Corridor", "age_bands":["under-13"], "permitted":["creative_tools","moderated_play","guardian_contacts","school_groups"], "disabled":["public_virality","adult_stranger_contact","behavioural_ads","algorithmic_feeds","livestreaming","sexualised_ai","location_sharing","monetisation"]},
    "COIL-C1": {"title":"Peer Corridor", "age_bands":["13-15"], "permitted":["verified_peer_contact","age_near_groups","chronological_feeds","limited_publishing","moderated_global_youth_spaces"], "disabled":["adult_recommender_escalation","adult_stranger_dm","public_virality_metrics","open_livestreaming","monetisation","sexualised_chatbots","adult_community_entry","harmful_recommender_routing"]},
    "COIL-C2": {"title":"Junior Global Culture Corridor", "age_bands":["13-15"], "permitted":["cross_border_youth_exchange","moderated_meme_remix","creative_collaboration","school_to_school_interaction","language_exchange"], "disabled":["adult_discovery","unbounded_group_growth","adult_recommender_escalation","behavioural_ads","open_livestreaming"], "required":["youth_specific_moderation","child_readable_rules","anti_dogpiling_controls","recommender_transparency"]},
    "COIL-C3": {"title":"Transitional Autonomy Corridor", "age_bands":["16-17"], "permitted":["broader_publication","broader_community_entry","partial_public_profile","optional_metrics_with_friction"], "disabled":["sexualised_ai_by_default","gambling_like_mechanics","predatory_contact_surfaces","high_pressure_monetisation","harmful_recommender_routing"]},
    "COIL-C4": {"title":"Adult Corridor", "age_bands":["18-plus"], "permitted":["ordinary_adult_access_subject_to_law"], "disabled":[]},
}

SCENARIOS = {
    "wrong-corridor": "Present a valid 13-15 credential to an under-13 corridor and verify refusal.",
    "revoked-replay": "Revoke a credential, replay a previously valid presentation, and verify refusal.",
    "forged-holder-signature": "Tamper with a holder signature and verify refusal.",
    "over-identification": "Record a simulated platform over-collection event for audit visibility.",
    "tampered-fieldgrade": "Return a synthetic tampered event chain verification result without mutating the real log.",
}


def now() -> int: return int(time.time())
def iso_now() -> str: return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
def canonical(data: Any) -> bytes: return json.dumps(data, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode()
def b64(b: bytes) -> str: return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def ub64(s: str) -> bytes: return base64.urlsafe_b64decode((s + "=" * (-len(s) % 4)).encode())
def sha_text(s: str) -> str: return hashlib.sha256(s.encode()).hexdigest()
def emit(x: Any) -> None: print(json.dumps(x, indent=2, ensure_ascii=False))


def default_corridor(age_band: str) -> str:
    return {"under-13":"COIL-C0", "13-15":"COIL-C1", "16-17":"COIL-C3", "18-plus":"COIL-C4"}.get(age_band, "COIL-C1")


def capabilities(age_band: str) -> List[str]:
    base = default_corridor(age_band)
    return [base] + (["COIL-C2"] if age_band == "13-15" else [])


def can_enter(age_band: str, requested: str, caps: List[str]) -> Tuple[bool, str]:
    if requested not in CAPABILITY_BANDS: return False, "unknown_corridor"
    if requested not in caps: return False, "credential_lacks_corridor_capability"
    if age_band not in CAPABILITY_BANDS[requested].get("age_bands", []): return False, "age_band_not_allowed_for_corridor"
    return True, "ok"


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir; data_dir.mkdir(parents=True, exist_ok=True)
        for name, default in {"credentials.json":[], "revocations.json":{}, "fieldgrade_log.jsonl":None}.items():
            p = data_dir / name
            if not p.exists(): p.write_text("" if default is None else json.dumps(default, indent=2), encoding="utf-8")
    def read_json(self, name: str, default: Any):
        try: return json.loads((self.data_dir / name).read_text("utf-8"))
        except Exception: return default
    def write_json(self, name: str, value: Any): (self.data_dir / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    def append_jsonl(self, name: str, value: Dict[str, Any]):
        with (self.data_dir / name).open("a", encoding="utf-8") as f: f.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")
    def read_jsonl(self, name: str, limit: int = 200) -> List[Dict[str, Any]]:
        p = self.data_dir / name
        rows=[]
        for line in p.read_text("utf-8").splitlines()[-limit:] if p.exists() else []:
            if line.strip():
                try: rows.append(json.loads(line))
                except Exception: pass
        return rows
    def clear(self):
        self.write_json("credentials.json", []); self.write_json("revocations.json", {}); (self.data_dir / "fieldgrade_log.jsonl").write_text("", encoding="utf-8")


class Signer:
    """HMAC demo signer. Production direction: Ed25519 + VC/VP + WebAuthn/passkeys."""
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir; data_dir.mkdir(parents=True, exist_ok=True)
        self.issuer_secret = self._secret("issuer_hmac_secret.key")
    def _secret(self, name: str) -> bytes:
        p = self.data_dir / name
        if not p.exists(): p.write_bytes(os.urandom(32))
        return p.read_bytes()
    def sign_issuer(self, payload: Dict[str, Any]) -> str: return b64(hmac.new(self.issuer_secret, canonical(payload), hashlib.sha256).digest())
    def verify_issuer(self, payload: Dict[str, Any], sig: str) -> bool:
        return hmac.compare_digest(hmac.new(self.issuer_secret, canonical(payload), hashlib.sha256).digest(), ub64(sig))
    def new_holder(self, key_id: str) -> Dict[str, str]:
        secret = os.urandom(32); (self.data_dir / f"holder_{key_id}.key").write_bytes(secret)
        return {"mode":"hmac-demo", "secret_hash":hashlib.sha256(secret).hexdigest()}
    def sign_holder(self, key_id: str, payload: Dict[str, Any]) -> str:
        secret = (self.data_dir / f"holder_{key_id}.key").read_bytes()
        return b64(hmac.new(secret, canonical(payload), hashlib.sha256).digest())
    def verify_holder(self, key_id: str, payload: Dict[str, Any], sig: str) -> bool:
        try:
            secret = (self.data_dir / f"holder_{key_id}.key").read_bytes()
            return hmac.compare_digest(hmac.new(secret, canonical(payload), hashlib.sha256).digest(), ub64(sig))
        except Exception: return False


class Fieldgrade:
    def __init__(self, store: Store): self.store = store
    def _last_hash(self) -> str:
        rows = self.store.read_jsonl("fieldgrade_log.jsonl", limit=1); return rows[-1]["hash"] if rows else "GENESIS"
    @staticmethod
    def hash_without_hash(e: Dict[str, Any]) -> str:
        x = dict(e); x.pop("hash", None); return hashlib.sha256(canonical(x)).hexdigest()
    def seal(self, event_type: str, actor: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        e = {"event_id":f"fg-{uuid.uuid4().hex}", "timestamp":iso_now(), "actor":actor, "event_type":event_type, "payload":payload, "previous_hash":self._last_hash()}
        e["hash"] = self.hash_without_hash(e); self.store.append_jsonl("fieldgrade_log.jsonl", e); return e
    def events(self, limit: int = 200) -> List[Dict[str, Any]]: return self.store.read_jsonl("fieldgrade_log.jsonl", limit=limit)
    def verify_chain(self, events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        events = events if events is not None else self.store.read_jsonl("fieldgrade_log.jsonl", limit=100000)
        prev="GENESIS"; failures=[]
        for i,e in enumerate(events):
            eh = self.hash_without_hash(e)
            if e.get("previous_hash") != prev: failures.append({"index":i,"type":"previous_hash_mismatch"})
            if e.get("hash") != eh: failures.append({"index":i,"type":"event_hash_mismatch"})
            prev = e.get("hash", "MISSING_HASH")
        return {"ok":not failures, "event_count":len(events), "head_hash":prev if events else "GENESIS", "failures":failures}
    def summary(self) -> Dict[str, Any]:
        ev = self.events(100000); chain = self.verify_chain(ev)
        return {"event_count":len(ev), "chain_ok":chain["ok"], "head_hash":chain["head_hash"], "events_by_type":dict(Counter(e.get("event_type") for e in ev)), "privacy_boundary":{"private_messages_logged":False,"biometric_templates_logged":False,"genetic_data_logged":False,"full_identity_required":False}}
    def audit_bundle(self) -> Dict[str, Any]:
        return {"schema":"fieldgrade-audit-bundle/v0.3-demo", "generated_at":iso_now(), "summary":self.summary(), "chain_verification":self.verify_chain(), "events":self.events(100000), "boundary":{"demo_only":True,"no_real_child_data":True,"no_network_biometrics":True,"no_genetic_identification":True,"not_legal_age_assurance":True}}


class Stack:
    def __init__(self, data_dir: Path):
        self.store = Store(data_dir); self.signer = Signer(data_dir); self.fg = Fieldgrade(self.store)
    def issue(self, alias: str, age_band: str) -> Dict[str, Any]:
        kid = f"hk-{uuid.uuid4().hex[:16]}"; cid = f"coil-{uuid.uuid4().hex}"; caps = capabilities(age_band); t=now()
        body = {"schema":"coil-hitt-credential/v0.3-demo", "credential_id":cid, "issuer":"local-demo-coil-issuer", "subject":{"holder_alias_hash":sha_text(alias), "age_band":age_band}, "capabilities":caps, "default_corridor":default_corridor(age_band), "binding":{"holder_key_id":kid, "holder_public":self.signer.new_holder(kid), "device_bound":True, "local_unlock_simulated":True}, "issued_at":t, "expires_at":t+31536000, "status":"active", "privacy_boundary":{"full_name_included":False,"full_date_of_birth_included":False,"biometric_template_included":False,"genetic_data_included":False,"universal_platform_identifier_included":False}}
        cred = {"body":body, "issuer_signature":self.signer.sign_issuer(body)}; creds=self.store.read_json("credentials.json", []); creds.append(cred); self.store.write_json("credentials.json", creds)
        self.fg.seal("credential.issued", "coil-issuer", {"credential_id":cid,"age_band":age_band,"capabilities":caps,"identity_minimised":True})
        return cred
    def credentials(self) -> List[Dict[str, Any]]: return self.store.read_json("credentials.json", [])
    def latest_id(self) -> str:
        creds = self.credentials()
        if not creds: raise SystemExit("No credentials. Run issue first.")
        return creds[-1]["body"]["credential_id"]
    def find(self, cid: str) -> Optional[Dict[str, Any]]:
        return next((c for c in self.credentials() if c.get("body",{}).get("credential_id") == cid), None)
    def revoke(self, cid: str, reason: str) -> Dict[str, Any]:
        rev = self.store.read_json("revocations.json", {}); rev[cid] = {"reason":reason,"revoked_at":now()}; self.store.write_json("revocations.json", rev); self.fg.seal("credential.revoked", "coil-issuer", {"credential_id":cid,"reason":reason}); return rev[cid]
    def present(self, cid: str, corridor: str) -> Dict[str, Any]:
        cred = self.find(cid)
        if not cred: raise SystemExit("credential_not_found")
        b=cred["body"]; age=b["subject"]["age_band"]; ok, reason = can_enter(age, corridor, b["capabilities"]); t=now()
        body={"schema":"hitt-presentation/v0.3-demo", "presentation_id":f"hitt-{uuid.uuid4().hex}", "credential_id":cid, "requested_corridor":corridor, "disclosed_claims":{"age_band":age,"corridor_allowed":ok,"corridor_reason":reason}, "holder_binding":{"holder_key_id":b["binding"]["holder_key_id"],"device_bound":True,"local_unlock_simulated":True}, "issued_at":t, "expires_at":t+300, "nonce":uuid.uuid4().hex}
        pres={"body":body, "holder_signature":self.signer.sign_holder(b["binding"]["holder_key_id"], body)}
        self.fg.seal("hitt.presented", "holder-wallet", {"credential_id":cid,"presentation_id":body["presentation_id"],"requested_corridor":corridor,"disclosed_claims":body["disclosed_claims"],"full_identity_disclosed":False})
        return pres
    def verify(self, pres: Dict[str, Any]) -> Dict[str, Any]:
        b=pres.get("body",{}); cid=b.get("credential_id"); cred=self.find(cid)
        def fail(reason: str, extra: Dict[str, Any] | None = None):
            r={"accepted":False,"reason":reason}; r.update(extra or {}); self.fg.seal("platform.verification_failed", "platform-verifier", r); return r
        if not cred: return fail("credential_not_found")
        cb=cred["body"]; rev=self.store.read_json("revocations.json", {})
        if cid in rev: return fail("credential_revoked", {"revocation":rev[cid]})
        if now() > int(cb.get("expires_at",0)): return fail("credential_expired")
        if now() > int(b.get("expires_at",0)): return fail("presentation_expired")
        if not self.signer.verify_issuer(cb, cred.get("issuer_signature","")): return fail("bad_issuer_signature")
        kid = cb["binding"]["holder_key_id"]
        if not self.signer.verify_holder(kid, b, pres.get("holder_signature","")): return fail("bad_holder_signature")
        requested=b.get("requested_corridor"); ok, reason=can_enter(cb["subject"]["age_band"], requested, cb["capabilities"])
        if not ok: return fail(reason, {"requested_corridor":requested})
        corridor=CAPABILITY_BANDS[requested]
        result={"accepted":True,"reason":"ok","corridor":requested,"corridor_title":corridor["title"],"platform_mode":{"permitted":corridor.get("permitted",[]),"disabled":corridor.get("disabled",[]),"required":corridor.get("required",[]),"behavioural_ads":False,"public_virality_by_default":False,"adult_stranger_contact":False},"data_minimisation":{"full_identity_received":False,"biometric_received":False,"genetic_data_received":False,"pairwise_pseudonymous_demo":True}}
        self.fg.seal("platform.corridor_instantiated", "platform-verifier", {"credential_id":cid,"presentation_id":b.get("presentation_id"),"corridor":requested,"corridor_title":corridor["title"],"disabled_features":corridor.get("disabled",[]),"data_minimised":True})
        return result


def run_scenario(data_dir: Path, scenario: str) -> Dict[str, Any]:
    s=Stack(data_dir)
    if scenario == "wrong-corridor":
        c=s.issue("sim-child", "13-15"); p=s.present(c["body"]["credential_id"], "COIL-C0"); r=s.verify(p); return {"scenario":scenario,"passed":r.get("accepted") is False,"result":r}
    if scenario == "revoked-replay":
        c=s.issue("sim-child", "13-15"); cid=c["body"]["credential_id"]; p=s.present(cid,"COIL-C1"); ok=s.verify(p); s.revoke(cid,"simulation_revoked_replay"); replay=s.verify(p); return {"scenario":scenario,"passed":ok.get("accepted") is True and replay.get("reason")=="credential_revoked","initial_result":ok,"replay_after_revocation":replay}
    if scenario == "forged-holder-signature":
        c=s.issue("sim-child", "13-15"); p=s.present(c["body"]["credential_id"],"COIL-C1"); p["holder_signature"]=p["holder_signature"][::-1]; r=s.verify(p); return {"scenario":scenario,"passed":r.get("reason")=="bad_holder_signature","result":r}
    if scenario == "over-identification":
        e=s.fg.seal("platform.policy_violation", "coil-sentinel", {"violation":"platform_requested_excessive_identity", "requested_fields":["full_name","full_date_of_birth","biometric_template"], "allowed_fields":["age_band","corridor_capability"], "privacy_boundary_triggered":True}); return {"scenario":scenario,"passed":True,"event":e}
    if scenario == "tampered-fieldgrade":
        c=s.issue("sim-child","13-15"); p=s.present(c["body"]["credential_id"],"COIL-C1"); s.verify(p); ev=s.fg.events(100000); tam=copy.deepcopy(ev); tam[-1]["payload"]["tampered"]=True; r=s.fg.verify_chain(tam); return {"scenario":scenario,"passed":r.get("ok") is False,"synthetic_tamper_result":r}
    raise SystemExit("unknown_scenario")


def selftest() -> None:
    with tempfile.TemporaryDirectory() as d:
        s=Stack(Path(d)); c=s.issue("demo-child","13-15"); p=s.present(c["body"]["credential_id"],"COIL-C1"); assert s.verify(p)["accepted"] is True
        bad=s.present(c["body"]["credential_id"],"COIL-C4"); assert s.verify(bad)["accepted"] is False
        c0=s.issue("demo-younger","under-13"); assert s.verify(s.present(c0["body"]["credential_id"],"COIL-C0"))["accepted"] is True
        for sc in SCENARIOS:
            with tempfile.TemporaryDirectory() as sd: assert run_scenario(Path(sd), sc)["passed"] is True
        assert s.fg.verify_chain()["ok"] is True
    print("selftest ok")


def main(argv: List[str] | None = None) -> int:
    ap=argparse.ArgumentParser(description="COIL/HITT/FIELDGRADE local stack v0.3")
    ap.add_argument("--data-dir", default=str(DATA_DIR)); sub=ap.add_subparsers(dest="cmd", required=True)
    pi=sub.add_parser("issue"); pi.add_argument("--age-band", default="13-15", choices=["under-13","13-15","16-17","18-plus"]); pi.add_argument("--alias", default="demo-child")
    sub.add_parser("list")
    pp=sub.add_parser("present"); pp.add_argument("--credential", default="latest"); pp.add_argument("--corridor", default="COIL-C1"); pp.add_argument("--out", default="latest_hitt.json")
    pv=sub.add_parser("verify"); pv.add_argument("--presentation", default="latest_hitt.json")
    pr=sub.add_parser("revoke"); pr.add_argument("--credential", default="latest"); pr.add_argument("--reason", default="operator_requested")
    pf=sub.add_parser("fieldgrade"); fs=pf.add_subparsers(dest="fg", required=True); fs.add_parser("verify"); fs.add_parser("summary"); fl=fs.add_parser("list"); fl.add_argument("--limit", type=int, default=25)
    pa=sub.add_parser("audit"); aa=pa.add_subparsers(dest="audit", required=True); ae=aa.add_parser("export"); ae.add_argument("--out", default="fieldgrade_audit_bundle.json")
    ps=sub.add_parser("simulate"); ps.add_argument("scenario", choices=sorted(SCENARIOS)); ps.add_argument("--isolated", action="store_true")
    sub.add_parser("selftest"); rz=sub.add_parser("reset"); rz.add_argument("--yes", action="store_true")
    a=ap.parse_args(argv); s=Stack(Path(a.data_dir))
    if a.cmd=="selftest": selftest(); return 0
    if a.cmd=="issue": emit(s.issue(a.alias, a.age_band)); return 0
    if a.cmd=="list": emit([{k:v for k,v in {"credential_id":c["body"]["credential_id"],"age_band":c["body"]["subject"]["age_band"],"capabilities":c["body"]["capabilities"],"default_corridor":c["body"]["default_corridor"],"status":c["body"]["status"]}.items()} for c in s.credentials()]); return 0
    if a.cmd=="present": cid=s.latest_id() if a.credential=="latest" else a.credential; p=s.present(cid, a.corridor); Path(a.out).write_text(json.dumps(p, indent=2), encoding="utf-8"); emit(p); return 0
    if a.cmd=="verify": r=s.verify(json.loads(Path(a.presentation).read_text("utf-8"))); emit(r); return 0 if r.get("accepted") else 2
    if a.cmd=="revoke": emit(s.revoke(s.latest_id() if a.credential=="latest" else a.credential, a.reason)); return 0
    if a.cmd=="fieldgrade":
        if a.fg=="verify": r=s.fg.verify_chain(); emit(r); return 0 if r.get("ok") else 3
        if a.fg=="summary": emit(s.fg.summary()); return 0
        if a.fg=="list": emit(s.fg.events(a.limit)); return 0
    if a.cmd=="audit":
        bundle=s.fg.audit_bundle(); Path(a.out).write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8"); emit({"ok":True,"out":a.out,"summary":bundle["summary"]}); return 0
    if a.cmd=="simulate":
        if a.isolated:
            with tempfile.TemporaryDirectory() as d: r=run_scenario(Path(d), a.scenario)
        else: r=run_scenario(Path(a.data_dir), a.scenario)
        emit(r); return 0 if r.get("passed") else 4
    if a.cmd=="reset":
        if not a.yes: raise SystemExit("Refusing to reset without --yes")
        s.store.clear(); emit({"ok":True,"reset":"demo_data_cleared"}); return 0
    return 1

if __name__ == "__main__": raise SystemExit(main())
