# Immich Gallery research and design notes

Date: July 30, 2026

This project reviewed
[`outadoc/immich-home-assistant`](https://github.com/outadoc/immich-home-assistant)
only to understand its behavior, known failures, and compatibility
requirements. No source code, text, or visual asset was copied from that
third-party repository.

## Legacy integration review

The legacy integration provides:

- a random-favorites image entity;
- one image entity for each selected album;
- URL, API-key, and album configuration through the Home Assistant UI;
- a fixed refresh interval of approximately five minutes.

The repository did not expose a license file during the review, so no
permission to copy or adapt its implementation was assumed. Immich Gallery
uses an independently written domain, API client, data model, config flow,
entity implementation, documentation, and test suite.

The review identified several design risks:

- A new HTTP session is created repeatedly instead of using Home Assistant's
  shared session.
- The favorite filter is sent as form-like text even though Immich 3.x expects
  a real JSON boolean, as reported in
  [issue #30](https://github.com/outadoc/immich-home-assistant/issues/30).
- The legacy options-flow pattern manually assigns `self.config_entry`, which
  broke with Home Assistant 2025.12, as reported in
  [issue #26](https://github.com/outadoc/immich-home-assistant/issues/26).
- Image refresh signaling does not match current `ImageEntity` behavior,
  causing images to change only after a restart in
  [issue #21](https://github.com/outadoc/immich-home-assistant/issues/21).
- Original assets are downloaded and only JPEG and PNG are accepted. HEIC,
  certificate, and empty-result failures appear together in
  [issue #24](https://github.com/outadoc/immich-home-assistant/issues/24).
- Failed downloads can enter an unbounded retry loop.
- API response bodies may be written to logs, potentially exposing personal
  media metadata.
- Complete album or asset lists are held in memory without explicit response
  or image-size limits.
- Reauthentication, reconfiguration, privacy-safe diagnostics, and automated
  test coverage are missing.
- The `immich` domain conflicts with Home Assistant's built-in
  [Immich integration](https://www.home-assistant.io/integrations/immich/).

These findings support a clean independent implementation instead of patching
or copying the legacy project.

## Official API contract

Immich recommends narrowly scoped API keys for third-party applications and
sends them in the `x-api-key` header:
[Authentication](https://api.immich.app/authentication).

The initial implementation uses only these stable endpoints:

| Purpose | Endpoint | Permission |
| --- | --- | --- |
| Server version | `GET /server/version` | Public |
| Current user | `GET /users/me` | `user.read` |
| Album list | `GET /albums` | `album.read` |
| Random image search | `POST /search/random` | `asset.read` |
| Preview image | `GET /assets/{id}/thumbnail?size=preview` | `asset.view` |

Primary references:
[server version](https://api.immich.app/endpoints/server/getServerVersion),
[current user](https://api.immich.app/endpoints/users/getMyUser),
[albums](https://api.immich.app/endpoints/albums/getAllAlbums),
[random search](https://api.immich.app/endpoints/search/searchRandom), and
[thumbnail](https://api.immich.app/endpoints/assets/viewAsset).

The integration does not request `asset.download`, write, delete, or
administrator permissions. The deprecated `/assets/random` endpoint is not
used.

## Architecture

The integration domain is `immich_gallery`, allowing it to coexist with Home
Assistant's built-in `immich` integration.

For each config entry:

1. Home Assistant's shared `aiohttp` session is reused.
2. A `DataUpdateCoordinator` runs at most three concurrent preview requests.
3. The entire library, favorites, and every selected album are separate
   sources and entities.
4. Immich returns a bounded server-random candidate set for each source.
5. Recently displayed assets are filtered from that candidate set.
6. Preview bytes are cached in the coordinator.
7. `ImageEntity.async_image()` returns cached bytes without network I/O.
8. `image_last_updated` changes after each successful coordinator refresh.
9. A source failure does not block other sources, and the last good preview
   remains cached.

This follows Home Assistant's
[image entity](https://developers.home-assistant.io/docs/core/entity/image/)
and
[data fetching](https://developers.home-assistant.io/docs/integration_fetching_data/)
guidance.

## Connection and reconfiguration

Setup and **Configure** use the same URL validation and normalization rules.
Both root URLs and URLs ending in `/api` are accepted.

Supported connection forms include:

- public or private HTTPS with a valid certificate;
- local HTTP with an explicit port;
- Tailscale IPv4 or IPv6 addresses;
- Tailscale MagicDNS hostnames;
- reverse proxies mounted under a subpath.

URLs containing credentials, query strings, or fragments are rejected. TLS
verification is enabled by default and should be disabled only when the user
deliberately trusts a private or self-signed certificate.

The **Configure** flow can update:

- the Immich host;
- an optional replacement API key;
- TLS verification;
- whole-library, favorite, and album sources;
- the per-source recent-image history window;
- the one-to-sixty-minute refresh interval.

No image source is enabled automatically. The user must explicitly select at
least one source. If a source is later deselected, its obsolete image entity is
removed from the entity registry rather than remaining unavailable.

Host and API-key changes are validated through real API requests before being
saved. The validated Immich user UUID must match the existing config entry, so
an entry cannot be moved accidentally to another account.

URL tests cover HTTPS, local HTTP, Tailscale IP addresses, MagicDNS, IPv6, and
reverse-proxy paths. An end-to-end local `aiohttp` test verifies headers,
endpoints, and preview handling. A user's private certificate and real
Tailscale peer must still be verified in that user's environment.

## Randomization for large libraries

The integration never downloads a complete library or album just to choose
one image. On every refresh:

1. Immich's stable `POST /search/random` endpoint is called with the source
   filter.
2. Candidate count is `recent-history window + 10`, clamped to 10–100.
3. Duplicate asset UUIDs returned by the server are removed.
4. UUIDs recently displayed by that source are excluded.
5. One remaining candidate is selected uniformly with `secrets.choice`.
6. If every candidate is recent, the least recently displayed candidate is
   selected instead of repeating the newest image.

Recent history is stored separately for every source in an in-memory `deque`.
The default window is 20 images. With the default five-minute refresh interval,
this represents roughly 100 minutes of recent display history when enough
distinct assets exist. Setting the window to `0` disables repeat avoidance.

Failed preview downloads are not added to history. At most 100 metadata rows
are requested per source, keeping the design bounded for large libraries while
cycling sensibly through small albums. History is not persisted and resets
when the integration reloads or Home Assistant restarts.

## Security and privacy decisions

- The API key is sent only in the `x-api-key` header, never in a URL or query.
- Server URLs containing user information, a query, or a fragment are
  rejected.
- HTTP redirects are not followed, preventing credentials from moving to
  another origin.
- TLS verification is enabled by default.
- Immich previews are requested instead of original files.
- Only AVIF, GIF, JPEG, PNG, and WebP response types are accepted.
- A 20 MiB limit is enforced through both `Content-Length` and streamed size.
- API response bodies, credentials, and media metadata are not logged.
- Entity state excludes filenames, EXIF, asset IDs, and capture dates.
- Diagnostics exclude URLs, credentials, user or entry IDs, album or asset
  IDs, filenames, and image content.
- There is no telemetry, analytics, cloud relay, or external error-reporting
  service.
- GitHub Actions dependencies are pinned to immutable commit hashes, and
  workflow permissions are limited to `contents: read`.

## Brand decision

Immich source code is distributed under AGPL-3.0:
[Immich license](https://github.com/immich-app/immich/blob/main/LICENSE).
That software license does not automatically grant trademark rights to the
Immich name or logo.

Immich's official [FAQ](https://docs.immich.app/FAQ/) limits uses that might
imply affiliation or endorsement while generally allowing integrations with
appropriate disclosure. The official
[Unraid installation guide](https://docs.immich.app/install/unraid/) directly
references the square Immich logo for visual identification.

The unmodified square Immich flower is therefore used only in the small local
HACS and Home Assistant technical icon assets. No Immich banner, screenshot,
wide wordmark, or marketing image is used in the GitHub README. Asset origin,
hashes, ownership, and license exclusion are documented in `BRANDING.md`.

Immich Gallery clearly states that it is an independent community integration
and is not affiliated with, sponsored by, or endorsed by Immich, FUTO, Home
Assistant, the Open Home Foundation, or HACS.

Home Assistant 2026.3 and newer support local brand assets for custom
integrations:
[Local brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/).
Runtime brand rendering therefore does not require an external service.

## HACS default-library admission

A valid `hacs.json` file alone does not place a repository in HACS's default
library. The official process requires:

1. a public, described, and topic-tagged repository with Issues enabled;
2. successful HACS Action and Hassfest checks without ignored validations;
3. a complete GitHub Release, not only a tag;
4. a pull request adding `"ofilis/ha-immich-gallery"` alphabetically to the
   `integration` list in `hacs/default`;
5. ongoing maintenance during review and after acceptance.

Official references:
[publishing](https://www.hacs.xyz/docs/publish/start/),
[integration requirements](https://www.hacs.xyz/docs/publish/integration/),
[validation](https://hacs.xyz/docs/publish/action/), and
[default inclusion](https://hacs.xyz/docs/publish/include/).

The detailed submission checklist is maintained in
`docs/HACS_SUBMISSION.md`.

## Initial scope

Implemented:

- random images from the entire library;
- random images from favorites;
- separate random image entities for multiple selected albums;
- a configurable one-to-sixty-minute refresh interval;
- host, API-key, TLS, source, history, and interval changes through Configure;
- UI setup, options flow, reauthentication, and reconfiguration;
- an English-only interface and project documentation;
- local Immich technical icon assets with documented source and hashes;
- HACS structure, submission guidance, MIT license, security policy, and CI;
- tests for API behavior, URL normalization, configuration, randomization,
  diagnostics, local HTTP, and stale entity cleanup.

Possible future work:

- person, date-range, rating, or location filters;
- ordered modes such as recently added;
- optional actions for advancing a dashboard card immediately;
- animation or video support;
- opt-in integration tests against a live Immich server.

Any new filter should request only the additional read permission it requires.
Write and delete capabilities remain outside the project scope.
