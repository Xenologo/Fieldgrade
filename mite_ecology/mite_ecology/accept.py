from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

# Termite verifier is a sibling package in this monorepo (termite_fieldpack/termite).
# When mite_ecology is run without installation, ensure termite is importable.
try:
    from termite.policy import load_policy
    from termite.verify import verify_bundle, VerifyResult
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path as _Path
    _root = _Path(__file__).resolve().parents[2]
    _tfp = _root / "termite_fieldpack"
    if _tfp.exists():
        sys.path.insert(0, str(_tfp))
    from termite.policy import load_policy
    from termite.verify import verify_bundle, VerifyResult

def verify_termite_bundle(
    bundle_path: Path,
    policy_path: Path,
    allowlist_path: Path,
) -> Tuple[VerifyResult, Any, Dict[str, Any]]:
    """Verify a Termite bundle using MEAP policy and allowlist.

    Returns (VerifyResult, policy_obj, allowlist_dict).
    The allowlist dict includes a helper key '_base_dir' used to resolve pubkey paths.
    """
    bundle_path = Path(bundle_path).resolve()
    policy_path = Path(policy_path).resolve()
    allowlist_path = Path(allowlist_path).resolve()

    policy = load_policy(policy_path)
    allowlist = yaml.safe_load(allowlist_path.read_text(encoding="utf-8")) or {}
    allowlist["_base_dir"] = str(allowlist_path.parent.resolve())

    vr = verify_bundle(bundle_path, policy=policy, allowlist=allowlist)
    return vr, policy, allowlist
