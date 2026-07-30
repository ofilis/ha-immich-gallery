# Changelog

All notable changes to Immich Gallery are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses semantic versioning.

## [Unreleased]

## [0.1.0] - 2026-07-30

### Changed

- Whole-library and favorite sources now require explicit selection instead
  of being enabled by default.
- The repeat-window field now explains that recent images are remembered
  separately for each source.
- Project documentation and the integration interface are English-only.

### Fixed

- Remove obsolete image entity-registry entries when their sources are
  deselected, preventing stale unavailable entities after reconfiguration.

### Added

- Initial Home Assistant config flow and image entities.
- Random library, favorites, and multiple-album sources.
- Editable host, API-key rotation, TLS verification, albums, repeat window,
  and refresh interval through the Configure flow.
- HTTPS, local HTTP, reverse-proxy path, Tailscale IP, MagicDNS, and IPv6 URL
  normalization.
- Server-side Immich random search with bounded candidate sampling,
  per-source recent-history filtering, duplicate removal, and least-recent
  fallback.
- Bounded Immich preview downloads with AVIF, GIF, JPEG, PNG, and WebP output.
- Privacy-preserving diagnostics, English localization, local branding,
  HACS/Hassfest validation, and automated tests.
- Small official Immich flower assets for HACS/Home Assistant identification,
  with documented upstream source, hash, and trademark exclusion; no banner
  or wide wordmark is included.

[Unreleased]: https://github.com/ofilis/ha-immich-gallery/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ofilis/ha-immich-gallery/releases/tag/v0.1.0
