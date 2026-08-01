"""Regression tests for HACS default-library metadata and branding."""

from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "custom_components"
INTEGRATION = COMPONENTS / "immich_gallery"
ASSETS = ROOT / "assets"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
REQUIRED_MANIFEST_KEYS = {
    "codeowners",
    "documentation",
    "domain",
    "issue_tracker",
    "name",
    "version",
}


def _png_dimensions(path: Path) -> tuple[int, int]:
    """Return dimensions from a PNG IHDR chunk."""
    content = path.read_bytes()

    assert content.startswith(PNG_SIGNATURE)
    assert content[12:16] == b"IHDR"
    return struct.unpack(">II", content[16:24])


def test_repository_contains_one_integration() -> None:
    """HACS integration repositories must contain exactly one component."""
    integrations = sorted(
        path.name
        for path in COMPONENTS.iterdir()
        if path.is_dir() and not path.name.startswith((".", "__"))
    )

    assert integrations == ["immich_gallery"]


def test_hacs_and_home_assistant_manifests_are_complete() -> None:
    """Required local metadata remains suitable for HACS validation."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

    assert manifest.keys() >= REQUIRED_MANIFEST_KEYS
    assert manifest["domain"] == "immich_gallery"
    assert manifest["name"] == "Immich Gallery"
    assert manifest["codeowners"] == ["@ofilis"]
    assert manifest["documentation"] == ("https://github.com/ofilis/ha-immich-gallery")
    assert manifest["issue_tracker"] == (
        "https://github.com/ofilis/ha-immich-gallery/issues"
    )
    assert hacs["name"] == "Immich Gallery"


def test_local_brand_icons_have_required_png_dimensions() -> None:
    """Local icons remain valid standard and high-density PNG assets."""
    brand = INTEGRATION / "brand"

    assert _png_dimensions(brand / "icon.png") == (256, 256)
    assert _png_dimensions(brand / "icon@2x.png") == (512, 512)
    assert (brand / "icon.png").read_bytes() == (ASSETS / "icon-256.png").read_bytes()
    assert (brand / "icon@2x.png").read_bytes() == (
        ASSETS / "icon-512.png"
    ).read_bytes()


def test_project_logo_assets_have_expected_dimensions() -> None:
    """The selected logo and its required icon sizes remain renderable."""
    expected_pngs = {
        "logo.png": (1254, 1254),
        "icon-256.png": (256, 256),
        "icon-512.png": (512, 512),
    }

    for filename, dimensions in expected_pngs.items():
        assert _png_dimensions(ASSETS / filename) == dimensions


def test_validation_workflow_has_hacs_and_hassfest_without_ignores() -> None:
    """Default inclusion requires both validators with no HACS ignores."""
    workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(
        encoding="utf-8"
    )

    assert "uses: hacs/action@" in workflow
    assert "uses: home-assistant/actions/hassfest@" in workflow
    assert "ignore:" not in workflow
