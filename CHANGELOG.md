# Changelog

All notable changes to Immich Gallery are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses semantic versioning.

## [Unreleased]

## [0.1.3] - 2026-08-02

### Fixed

- Export the repository logo and bundled Home Assistant/HACS icons as RGBA PNGs,
  removing both the exterior background and every neutral-white separator.

## [0.1.2] - 2026-08-02

### Changed

- Use the selected Immich Gallery house-and-landscape logo consistently in the
  README, HACS, and Home Assistant.
- Rewrite the README around installation, setup, dashboard use, configuration,
  privacy, and security while removing maintainer-only implementation detail.
- Use the project owner's GitHub handle in the MIT copyright notice.

## [0.1.1] - 2026-07-30

### Changed

- Remove the unused optional loading dependency on Home Assistant's built-in
  `immich` integration. Immich Gallery remains an independent integration and
  continues to communicate directly with the configured Immich API.
- Document the HACS 2.0.5 local-brand display limitation, the separate
  repository-list and update-entity fixes being developed upstream, and the
  exact default-library submission process.
- Clarify that HACS does not require README screenshots for integrations and
  that no banner or personal library image will be published.

### Added

- Regression tests for the one-integration repository structure, required HACS
  and Home Assistant metadata, local icon PNG dimensions, and validation
  workflow configuration.

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

[Unreleased]: https://github.com/ofilis/ha-immich-gallery/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/ofilis/ha-immich-gallery/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/ofilis/ha-immich-gallery/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/ofilis/ha-immich-gallery/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ofilis/ha-immich-gallery/releases/tag/v0.1.0
