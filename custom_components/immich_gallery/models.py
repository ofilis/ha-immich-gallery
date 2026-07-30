"""Data models for Immich Gallery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class SourceKind(StrEnum):
    """Supported gallery source kinds."""

    LIBRARY = "library"
    FAVORITES = "favorites"
    ALBUM = "album"


@dataclass(frozen=True, slots=True)
class Album:
    """A selectable Immich album."""

    album_id: str
    name: str


@dataclass(frozen=True, slots=True)
class GallerySource:
    """A configured image source."""

    key: str
    kind: SourceKind
    name: str
    album_id: str | None = None


@dataclass(frozen=True, slots=True)
class AssetMetadata:
    """Minimal non-binary asset metadata used by Home Assistant."""

    asset_id: str


@dataclass(frozen=True, slots=True)
class GalleryImage:
    """A downloaded gallery preview."""

    asset_id: str
    content: bytes
    content_type: str
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class GalleryData:
    """Coordinator data for all configured sources."""

    images: dict[str, GalleryImage] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Validated Immich connection details."""

    user_id: str
    user_name: str
    server_version: str
    albums: tuple[Album, ...]
