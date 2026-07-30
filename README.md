<p align="center">
  A privacy-first Home Assistant integration for rotating images from your
  self-hosted Immich library.
</p>

<p align="center">
  <a href="https://github.com/ofilis/ha-immich-gallery/actions/workflows/validate.yml">
    <img src="https://github.com/ofilis/ha-immich-gallery/actions/workflows/validate.yml/badge.svg" alt="HACS and Hassfest validation">
  </a>
  <a href="https://github.com/ofilis/ha-immich-gallery/actions/workflows/tests.yml">
    <img src="https://github.com/ofilis/ha-immich-gallery/actions/workflows/tests.yml/badge.svg" alt="Tests">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/ofilis/ha-immich-gallery" alt="MIT license">
  </a>
</p>

# Immich Gallery

Immich Gallery creates rotating Home Assistant `image` entities from an Immich
library. It supports the entire library, favorites, and any number of selected
albums.

It complements Home Assistant's built-in
[Immich integration](https://www.home-assistant.io/integrations/immich/).
The unique domain `immich_gallery` means both integrations can run in the same
Home Assistant instance without shadowing each other.

> [!IMPORTANT]
> Immich Gallery is an independent community project. It is not affiliated
> with, sponsored by, or endorsed by Immich, FUTO, Home Assistant, the Open
> Home Foundation, or HACS.

## Highlights

- Random image from the entire Immich library
- Random image from favorites
- One separate image entity for every selected album
- Configurable rotation interval from 1 to 60 minutes
- Per-source recent-image memory to reduce visible repeats
- Host, API-key rotation, TLS, albums, randomization, and timing editable later
  through the integration's **Configure** button
- HTTPS, local HTTP, reverse-proxy paths, Tailscale IP addresses, and Tailscale
  MagicDNS hostnames
- Immich-generated previews instead of original-file downloads
- HEIC, HEIF, RAW, TIFF, and other source formats when Immich can generate a
  browser-safe preview
- UI setup, reauthentication, reconfiguration, English, and Turkish
- No telemetry, cloud relay, analytics, or third-party runtime service

## Requirements

- Home Assistant 2026.4 or newer
- HACS
- A reachable Immich server
- A dedicated Immich API key with only:

  - `user.read`
  - `album.read`
  - `asset.read`
  - `asset.view`

Do not grant `all`, upload, update, delete, administration, or
`asset.download` permissions.

## Installation

### From the default HACS library

This will become the preferred route after the repository is accepted:

1. Open **HACS**.
2. Search for **Immich Gallery**.
3. Select **Download**.
4. Restart Home Assistant when HACS requests it.
5. Go to **Settings → Devices & services → Add integration**.
6. Select **Immich Gallery**.

Default-library admission requires a public release and an accepted pull
request in `hacs/default`. Until that review is complete, use the transitional
custom-repository method below.

### Transitional custom-repository installation

1. Open **HACS**.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/ofilis/ha-immich-gallery`.
4. Select the **Integration** category.
5. Download **Immich Gallery** and restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration**.
7. Select **Immich Gallery**.

## Initial setup

Enter the root address of the Immich instance and the dedicated API key.
Both root URLs and URLs ending in `/api` are accepted.

Supported examples:

```text
https://photos.example.com
https://example.com/immich
http://192.168.1.42:2283
http://100.64.12.34:2283
https://immich.my-tailnet.ts.net
```

API keys are sent only in the `x-api-key` request header. They are never
inserted into an image URL or query string.

TLS verification is enabled by default. Disable it only for a deliberately
self-signed/private certificate on a trusted path. Plain local HTTP and
Tailscale HTTP are supported, but HTTPS remains preferable whenever the
network design allows it.

After validation, select at least one source:

- entire library;
- favorites;
- one or more albums.

Each enabled source creates its own `image` entity.

## Changing the configuration later

Open:

**Settings → Devices & services → Immich Gallery → Configure**

The Configure screen exposes:

| Setting | Purpose |
| --- | --- |
| Immich host | Move between HTTPS, LAN HTTP, reverse proxy, or Tailscale |
| New API key | Rotate the credential; leave blank to keep the stored key |
| Verify TLS certificate | Keep enabled unless a trusted private certificate requires otherwise |
| Entire library | Enable or disable the library entity |
| Favorites | Enable or disable the favorites entity |
| Albums | Add or remove album entities |
| Recently shown images to avoid | Per-source repeat-protection window, 0–100 |
| Refresh interval | Minutes between rotations, 1–60 |

A changed host or key is validated before it is stored. The new endpoint must
resolve to the same Immich user, preventing an accidental switch to an
unrelated account under the existing config entry.

## Randomization design

Large libraries must not be downloaded into Home Assistant just to select one
photo. Immich Gallery therefore uses Immich's stable
[`POST /search/random`](https://api.immich.app/endpoints/search/searchRandom)
endpoint with the relevant library, favorites, or album filter.

For every source and rotation:

1. Immich performs the random selection on the server across all matching
   images.
2. The integration requests a bounded candidate batch. Its size is the
   configured recent-history window plus 10, clamped to 10–100.
3. Duplicate asset IDs in the response are removed.
4. Candidates displayed recently by that source are excluded.
5. One remaining candidate is selected uniformly with Python's
   cryptographic random selector.
6. If every returned candidate belongs to the recent history, the least
   recently displayed candidate is used instead of immediately repeating the
   newest image.

This remains scalable for very large libraries because at most 100 metadata
rows are requested per source. It also behaves sensibly for small albums by
cycling toward the least recently seen item.

Recent asset IDs exist only in runtime memory. They are not written to Home
Assistant state, diagnostics, logs, or this repository, and the history resets
when the integration reloads or Home Assistant restarts.

## Image formats

The source file format is intentionally separated from the displayed format.
Immich Gallery requests:

```text
GET /api/assets/{id}/thumbnail?size=preview
```

Immich performs its normal preview generation, so an original HEIC, HEIF, RAW,
TIFF, or other supported source can be displayed without Home Assistant
downloading the original file.

The integration accepts browser-safe preview responses in AVIF, GIF, JPEG,
PNG, and WebP. SVG is deliberately rejected, and every preview is limited to
20 MiB. If Immich cannot generate a supported preview for an asset, that
source remains unavailable for the current cycle while its last good image is
preserved.

## Dashboard examples

The final entity ID is assigned by Home Assistant and can be edited from the
entity settings.

### Picture entity

```yaml
type: picture-entity
entity: image.immich_gallery_random_library
show_name: false
show_state: false
fit_mode: contain
```

### Favorites

```yaml
type: picture-entity
entity: image.immich_gallery_random_favorites
show_name: false
show_state: false
fit_mode: contain
tap_action:
  action: more-info
```

Selected albums appear as separate image entities named after the albums.

## Privacy and security

- Runtime traffic goes only from Home Assistant to the configured Immich host.
- No telemetry, analytics, crash-reporting service, or cloud relay exists.
- Redirects are rejected so the API key cannot be forwarded to another host.
- User-supplied URLs containing credentials, query strings, or fragments are
  rejected.
- Server-provided user, album, and asset IDs are validated as UUIDs before
  being used.
- Only previews are downloaded; original assets are never requested.
- Image MIME types and response sizes are restricted.
- The API key, host, user ID, album IDs, asset IDs, filenames, EXIF data, and
  image bytes are excluded from diagnostics.
- Entity state exposes no filename, EXIF, asset ID, or capture time.
- GitHub Actions use read-only repository permissions and immutable commit
  SHAs.

Like any API credential stored by Home Assistant, the key remains available to
an administrator with access to Home Assistant's private storage. Protect Home
Assistant backups and configuration storage accordingly.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and credential
response guidance.

## Branding

The small integration icon uses the official Immich flower so the connection
to Immich remains immediately recognizable in HACS and Home Assistant. No
Immich banner, wide wordmark, screenshot, or marketing image is displayed in
this README.

Immich and its flower mark belong to their respective owner and are not
covered by this repository's MIT license. Their use identifies compatibility
and does not imply sponsorship or endorsement. Local brand files avoid a
runtime request to an external branding service.

See [BRANDING.md](BRANDING.md) for the exact upstream source, hash, attribution,
and the non-affiliation notice.

## Migration from older custom integrations

Older custom components using the `immich` domain collide with Home Assistant's
built-in Immich integration. Remove or disable the old custom component before
restarting Home Assistant.

Immich Gallery uses the separate `immich_gallery` domain. Entity IDs from an
older component are not migrated automatically; update dashboard cards and
automations after installation.

## HACS default-library status

The repository is structured for HACS and Hassfest validation. The complete
submission sequence and maintainer checklist are documented in
[docs/HACS_SUBMISSION.md](docs/HACS_SUBMISSION.md).

HACS notes that new default-repository reviews can take months. During that
period, the same release can be installed through the custom-repository route.

## Development

```bash
python -m pip install -r requirements_test.txt
ruff check .
ruff format --check .
python -m pytest
```

The test suite covers URL safety, HTTPS/LAN/Tailscale address normalization,
real loopback HTTP communication, request headers, permissions, bounded image
downloads, path-injection prevention, recent-history randomization, Configure
fields, and privacy-safe diagnostics.

The project was independently implemented against the public Immich API and
Home Assistant developer documentation. Third-party integration source was not
copied. See [RESEARCH.md](RESEARCH.md) for the clean-room findings and design
decisions.

## Contributing

Bug reports and focused pull requests are welcome. Never attach real API keys,
private hostnames, album or asset IDs, filenames, EXIF data, or private library
screenshots to a public issue.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a change.

## License

Integration code and original project material: MIT © 2026 Okan Filis.
Third-party names, logos, and trademarks are excluded; see
[BRANDING.md](BRANDING.md).
