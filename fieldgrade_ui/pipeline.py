from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .storage import publish_bundle_if_configured

def run_cmd(
    cmd: list[str],
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    log: Optional[Callable[[str], None]] = None,
) -> tuple[int, str, str]:
    """Run a subprocess with a configurable timeout.

    Timeout is controlled by FG_CMD_TIMEOUT_S (default 600). Set to 0/empty to disable.
    """
    if log:
        log(f"$ {' '.join(cmd)} (cwd={cwd})")

    timeout_s_raw = (os.environ.get("FG_CMD_TIMEOUT_S", "600") or "600").strip()
    try:
        timeout_s = float(timeout_s_raw)
    except Exception:
        timeout_s = 600.0
    if timeout_s <= 0:
        timeout_s = None

    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
        rc = int(p.returncode)
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
    except subprocess.TimeoutExpired as e:
        rc = 124
        out = (e.stdout or "") if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
        err = (e.stderr or "") if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", "replace")
        out = (out or "").strip()
        err = (err or "").strip() + f"\n[timeout] command exceeded {timeout_s_raw}s"

    if log and out:
        log(out)
    if log and err:
        log(err)
    return rc, out, err

def run_termite_to_ecology_pipeline(
    repo_root: Path,
    upload_path: Path,
    label: str,
    run_id: Optional[str] = None,
    policy_path: Optional[Path] = None,
    allowlist_path: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    runner = (os.environ.get("FG_PIPELINE_RUNNER") or "subprocess").strip().lower()
    if runner in ("lib", "library", "inprocess"):
        from .internal_pipeline import run_termite_to_ecology_pipeline_library

        if log:
            log("pipeline: using in-process library runner (FG_PIPELINE_RUNNER=library)")
        return run_termite_to_ecology_pipeline_library(
            repo_root,
            upload_path=upload_path,
            label=label,
            run_id=run_id,
            policy_path=policy_path,
            allowlist_path=allowlist_path,
            log=log,
        )

    rid = (run_id or "").strip() or uuid.uuid4().hex

    def _env(stage: str) -> dict[str, str]:
        e = dict(os.environ)
        e["FG_RUN_ID"] = rid
        # Trace IDs are stage-scoped to make operator correlation easier.
        e["FG_TRACE_ID"] = f"{rid}:{stage}"
        return e

    # Paths
    fieldpack_dir = repo_root / "termite_fieldpack"
    ecology_dir = repo_root / "mite_ecology"

    py = sys.executable

    if not upload_path.exists():
        raise FileNotFoundError(str(upload_path))

    if log:
        log(f"pipeline: upload_path={upload_path}")
        log(f"pipeline: label={label}")

    # 1) termite ingest
    rc, out, err = run_cmd(
        [py, "-m", "termite.cli", "ingest", str(upload_path)],
        cwd=fieldpack_dir,
        env=_env("termite_ingest"),
        log=log,
    )
    if rc != 0:
        raise RuntimeError(f"termite ingest failed rc={rc}: {err or out}")
    ingest_json = json.loads(out) if out else {}

    # 2) termite seal
    rc, out, err = run_cmd(
        [py, "-m", "termite.cli", "seal", "--label", label],
        cwd=fieldpack_dir,
        env=_env("termite_seal"),
        log=log,
    )
    if rc != 0:
        raise RuntimeError(f"termite seal failed rc={rc}: {err or out}")
    bundle_path = Path(out.strip())

    bundle_store_info: Dict[str, Any] = {}
    try:
        stored = publish_bundle_if_configured(repo_root, bundle_path)
        if stored is not None:
            bundle_store_info = {
                "bundle_store": (os.environ.get("FG_BUNDLE_STORE") or "").strip() or "s3",
                "bundle_store_key": stored.key,
                "bundle_sha256": stored.sha256,
                "bundle_uri": stored.uri,
            }
            if log:
                log(f"bundle published: {stored.uri} (sha256={stored.sha256})")
    except Exception as e:
        # Publishing is optional; keep pipeline semantics unchanged.
        if log:
            log(f"bundle publish skipped/failed: {type(e).__name__}: {e}")

    # 3) termite verify
    if policy_path is None:
        policy_path = fieldpack_dir / "config" / "meap_v1.yaml"
    if allowlist_path is None:
        allowlist_path = fieldpack_dir / "config" / "tool_allowlist.yaml"

    rc, out, err = run_cmd(
        [py, "-m", "termite.cli", "verify", str(bundle_path), "--policy", str(policy_path), "--allowlist", str(allowlist_path)],
        cwd=fieldpack_dir,
        env=_env("termite_verify"),
        log=log,
    )
    if rc != 0:
        raise RuntimeError(f"termite verify failed rc={rc}: {err or out}")
    verify_json = json.loads(out) if out else {}
    if not verify_json.get("ok", False):
        raise RuntimeError(f"termite verify not ok: {verify_json}")

    # 4) mite_ecology init
    rc, out, err = run_cmd([py, "-m", "mite_ecology.cli", "init"], cwd=ecology_dir, env=_env("ecology_init"), log=log)
    if rc != 0:
        raise RuntimeError(f"mite_ecology init failed rc={rc}: {err or out}")

    # 5) import bundle
    rc, out, err = run_cmd(
        [py, "-m", "mite_ecology.cli", "import-bundle", str(bundle_path), "--idempotent"],
        cwd=ecology_dir,
        env=_env("ecology_import"),
        log=log,
    )
    if rc != 0:
        raise RuntimeError(f"mite_ecology import-bundle failed rc={rc}: {err or out}")

    # 6) auto-run
    rc, out, err = run_cmd([py, "-m", "mite_ecology.cli", "auto-run"], cwd=ecology_dir, env=_env("ecology_auto_run"), log=log)
    if rc != 0:
        raise RuntimeError(f"mite_ecology auto-run failed rc={rc}: {err or out}")

    # 7) replay-verify
    rc, out, err = run_cmd([py, "-m", "mite_ecology.cli", "replay-verify"], cwd=ecology_dir, env=_env("ecology_replay_verify"), log=log)
    if rc != 0:
        raise RuntimeError(f"mite_ecology replay-verify failed rc={rc}: {err or out}")
    replay_json = json.loads(out) if out else {}

    return {
        "ingest": ingest_json,
        "bundle_path": str(bundle_path),
        "verify": verify_json,
        "replay_verify": replay_json,
        "run_id": rid,
        **bundle_store_info,
    }
