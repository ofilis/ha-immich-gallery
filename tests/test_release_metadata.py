"""Tests for release metadata consistency."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "immich_gallery" / "manifest.json"


def test_current_version_has_changelog_and_release_notes() -> None:
    """The manifest version always has curated release metadata."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version = manifest["version"]

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    release_notes = ROOT / "docs" / "releases" / f"v{version}.md"

    assert f"## [{version}]" in changelog
    assert release_notes.is_file()
    assert release_notes.read_text(encoding="utf-8").startswith(
        f"# Immich Gallery {version}\n"
    )
