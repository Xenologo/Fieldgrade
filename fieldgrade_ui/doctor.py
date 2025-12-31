from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]

def check() -> Dict[str, object]:
    root = _repo_root()
    checks: List[Tuple[str, bool, str]] = []

    def ok(name: str, condition: bool, detail: str) -> None:
        checks.append((name, condition, detail))

    ok("python", True, sys.version.replace("\n"," "))
    ok("platform", True, f"{platform.system()} {platform.machine()}")

    # executables
    for exe in ["git", "zip", "unzip"]:
        ok(f"exe:{exe}", shutil.which(exe) is not None, shutil.which(exe) or "missing")

    # termux signals
    ok("termux", "com.termux" in (os.environ.get("PREFIX","") + os.environ.get("HOME","")), os.environ.get("PREFIX",""))
    ok("repo_root", root.exists(), str(root))

    # expected dirs
    for d in ["mite_ecology", "termite_fieldpack", "fieldgrade_ui"]:
        ok(f"dir:{d}", (root/d).exists(), str(root/d))

    # deps (soft)
    deps = ["fastapi", "uvicorn", "multipart"]
    for dep in deps:
        try:
            __import__(dep if dep != "multipart" else "multipart")
            ok(f"py:{dep}", True, "ok")
        except Exception as e:
            ok(f"py:{dep}", False, str(e))

    return {"checks": [{"name": n, "ok": b, "detail": d} for (n,b,d) in checks]}

def main() -> None:
    import json
    print(json.dumps(check(), indent=2))

if __name__ == "__main__":
    main()
