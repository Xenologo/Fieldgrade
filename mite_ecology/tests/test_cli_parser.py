from __future__ import annotations


def test_cli_build_parser_has_no_duplicate_subcommands() -> None:
    # Importing and building the parser should not raise.
    from mite_ecology.cli import build_parser

    p = build_parser()

    # Introspect subcommand names from argparse internals.
    subparsers_actions = [
        a for a in p._actions  # type: ignore[attr-defined]
        if getattr(a, "dest", None) == "cmd"
    ]
    assert subparsers_actions, "expected subparsers action"

    choices = getattr(subparsers_actions[0], "choices", {})
    assert isinstance(choices, dict)

    # Critical commands we expect to exist.
    assert "release-build" in choices
    assert "release-verify" in choices
