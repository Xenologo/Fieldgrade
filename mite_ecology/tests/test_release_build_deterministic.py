from __future__ import annotations

from pathlib import Path
import time

from mite_ecology.release import build_release, release_zip_sha256


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_release_build_is_deterministic(tmp_path: Path) -> None:
    # Minimal valid registries that satisfy the JSON Schemas.
    comps = tmp_path / "components.yaml"
    vars_ = tmp_path / "variants.yaml"
    rems = tmp_path / "remotes.yaml"

    _write(
        comps,
        "\n".join(
            [
                "type: registry_components/1.0",
                "version: '1.0'",
                "components:",
                "  - component_id: demo_component",
            ]
        )
        + "\n",
    )

    _write(
        vars_,
        "\n".join(
            [
                "type: registry_variants/1.0",
                "version: '1.0'",
                "variants:",
                "  - variant_id: demo_variant",
            ]
        )
        + "\n",
    )

    _write(
        rems,
        "\n".join(
            [
                "type: registry_remotes/1.0",
                "version: '1.0'",
                "remotes: []",
            ]
        )
        + "\n",
    )

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    r1 = build_release(
        out_dir=out1,
        components_path=comps,
        variants_path=vars_,
        remotes_path=rems,
    )

    # Ensure wall-clock time does not affect the artifact.
    time.sleep(1.1)

    r2 = build_release(
        out_dir=out2,
        components_path=comps,
        variants_path=vars_,
        remotes_path=rems,
    )

    assert r1.release_id == r2.release_id
    assert r1.manifest_sha256 == r2.manifest_sha256

    # Zip bytes should also be stable.
    assert release_zip_sha256(r1.zip_path) == release_zip_sha256(r2.zip_path)
