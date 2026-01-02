from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


@dataclass(frozen=True)
class RemoteSyncResult:
    remote_id: str
    ok: bool
    ts: float
    tuf_base: str
    targets: Dict[str, Dict[str, Any]]
    error: Optional[str] = None
    skipped: bool = False


def _repo_root() -> Path:
    # .../fg_next/mite_ecology/mite_ecology/remote_sync.py -> parents[2] == .../fg_next
    return Path(__file__).resolve().parents[2]


def _safe_remote_id(remote_id: str) -> str:
    s = (remote_id or "").strip()
    out = []
    for ch in s:
        if ch.isalnum() or ch in ("-", "_", "."):
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)[:80] or "remote"


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def status_path(cache_root: str | Path, remote_id: str) -> Path:
    rid = _safe_remote_id(remote_id)
    return Path(cache_root) / rid / "status.json"


def load_status(cache_root: str | Path, remote_id: str) -> Optional[Dict[str, Any]]:
    return _read_json(status_path(cache_root, remote_id))


def _resolve_root_path(root_path: str) -> Path:
    p = Path(root_path).expanduser()
    if p.is_absolute():
        return p
    return _repo_root() / p


def _target_map(remote: Dict[str, Any]) -> Dict[str, str]:
    # Default target names expected on the remote TUF repository.
    defaults = {
        "components": "components_v1.yaml",
        "variants": "variants_v1.yaml",
        "remotes": "remotes_v1.yaml",
    }

    cfg = remote.get("targets")
    if isinstance(cfg, dict):
        out = dict(defaults)
        for k, v in cfg.items():
            if k in out and isinstance(v, str) and v.strip():
                out[k] = v.strip()
        return out

    return defaults


def sync_remote(
    remote: Dict[str, Any],
    *,
    cache_root: str | Path,
    ttl_seconds: int = 0,
) -> RemoteSyncResult:
    """Sync a single remote using TUF verification.

    Expects remote dict fields:
      - remote_id: str
      - tuf_base: str (base URL)
      - trust.root_path: str (path to root.json trust bootstrap)
      - targets: optional mapping to target paths

    Stores:
      - {cache_root}/{remote_id}/status.json
      - {cache_root}/{remote_id}/targets/*.yaml (downloaded and verified)
    """

    remote_id = (remote.get("remote_id") or "").strip()
    tuf_base = (remote.get("tuf_base") or "").strip()

    trust_val = remote.get("trust")
    trust: Dict[str, Any] = trust_val if isinstance(trust_val, dict) else {}
    root_path_raw = (trust.get("root_path") or "").strip()

    if not remote_id or not tuf_base:
        return RemoteSyncResult(
            remote_id=remote_id or "(missing)",
            ok=False,
            ts=time.time(),
            tuf_base=tuf_base,
            targets={},
            error="missing_remote_id_or_tuf_base",
        )

    if not root_path_raw:
        return RemoteSyncResult(
            remote_id=remote_id,
            ok=False,
            ts=time.time(),
            tuf_base=tuf_base,
            targets={},
            error="missing_trust_root_path",
        )

    rid = _safe_remote_id(remote_id)
    root = Path(cache_root) / rid
    st_path = root / "status.json"

    if ttl_seconds and ttl_seconds > 0 and st_path.exists():
        try:
            age = time.time() - st_path.stat().st_mtime
            if age < ttl_seconds:
                prev = _read_json(st_path) or {}
                prev["skipped"] = True
                prev["ts"] = time.time()
                _write_json(st_path, prev)
                return RemoteSyncResult(
                    remote_id=remote_id,
                    ok=bool(prev.get("ok")),
                    ts=float(prev.get("ts") or time.time()),
                    tuf_base=tuf_base,
                    targets=dict(prev.get("targets") or {}),
                    error=prev.get("error"),
                    skipped=True,
                )
        except Exception:
            # ignore TTL failures; fall through to a real sync
            pass

    try:
        from tuf.ngclient.updater import Updater
        from tuf.ngclient.config import UpdaterConfig

        # Registry loaders validate schemas + canonicalize/hashes for us.
        from .registry import load_components_registry, load_remotes_registry, load_variants_registry
    except Exception as e:
        return RemoteSyncResult(
            remote_id=remote_id,
            ok=False,
            ts=time.time(),
            tuf_base=tuf_base,
            targets={},
            error=f"tuf_unavailable: {e}",
        )

    try:
        tuf_base = tuf_base.rstrip("/")
        metadata_base_url = tuf_base + "/metadata/"
        target_base_url = tuf_base + "/targets/"

        meta_dir = root / "metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)
        targets_dir = root / "targets"
        targets_dir.mkdir(parents=True, exist_ok=True)

        root_path = _resolve_root_path(root_path_raw)
        bootstrap = root_path.read_bytes()

        config = UpdaterConfig(
            # keep the defaults, but prevent unbounded metadata reads
            root_max_length=512000,
            timestamp_max_length=16384,
            snapshot_max_length=2000000,
            targets_max_length=5000000,
            app_user_agent="fieldgrade/remote-sync",
        )

        updater = Updater(
            metadata_dir=str(meta_dir),
            metadata_base_url=metadata_base_url,
            target_dir=str(targets_dir),
            target_base_url=target_base_url,
            config=config,
            bootstrap=bootstrap,
        )

        updater.refresh()

        targets_cfg = _target_map(remote)
        out_targets: Dict[str, Dict[str, Any]] = {}

        def _dl(kind: str, tpath: str) -> None:
            info = updater.get_targetinfo(tpath)
            if info is None:
                out_targets[kind] = {"ok": False, "error": f"target_not_found: {tpath}", "path": None}
                return
            dest = targets_dir / f"{kind}.yaml"
            updater.download_target(info, filepath=str(dest))

            # Validate and compute canonical hash.
            if kind == "components":
                r = load_components_registry(dest)
            elif kind == "variants":
                r = load_variants_registry(dest)
            else:
                r = load_remotes_registry(dest)

            out_targets[kind] = {
                "ok": True,
                "target_path": tpath,
                "path": str(dest),
                "canonical_sha256": r.canonical_sha256,
            }

        for kind, tpath in targets_cfg.items():
            _dl(kind, tpath)

        ok = all(v.get("ok") is True for v in out_targets.values())
        result = RemoteSyncResult(
            remote_id=remote_id,
            ok=ok,
            ts=time.time(),
            tuf_base=tuf_base,
            targets=out_targets,
            error=None if ok else "one_or_more_targets_failed",
        )

        _write_json(st_path, asdict(result))
        return result

    except Exception as e:
        result = RemoteSyncResult(
            remote_id=remote_id,
            ok=False,
            ts=time.time(),
            tuf_base=tuf_base,
            targets={},
            error=f"sync_failed: {e}",
        )
        try:
            _write_json(st_path, asdict(result))
        except Exception:
            pass
        return result


def sync_all_remotes(
    remotes: Iterable[Dict[str, Any]],
    *,
    cache_root: str | Path,
    only_remote_id: str | None = None,
) -> list[RemoteSyncResult]:
    out: list[RemoteSyncResult] = []
    want = (only_remote_id or "").strip()

    for r in remotes:
        if not isinstance(r, dict):
            continue
        rid = (r.get("remote_id") or "").strip()
        if want and rid != want:
            continue
        if r.get("enabled") is False:
            continue

        ttl = 0
        cache_val = r.get("cache")
        cache_cfg: Dict[str, Any] = cache_val if isinstance(cache_val, dict) else {}
        ttl_val = cache_cfg.get("ttl_seconds")
        if isinstance(ttl_val, int):
            ttl = ttl_val

        out.append(sync_remote(r, cache_root=cache_root, ttl_seconds=ttl))

    return out
