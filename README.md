<p align="center">
  <img src="assets/logo.png" width="180" alt="Immich Gallery logo">
</p>

<div align="center">

# Immich Gallery

**Bring your self-hosted Immich photos into Home Assistant.**

Display a rotating photo from your entire library, favorites, or selected albums —
with no cloud relay or third-party service.

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/default)
[![Home Assistant 2026.4+](https://img.shields.io/badge/Home%20Assistant-2026.4%2B-18BCF2.svg)](https://www.home-assistant.io/)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

## What is Immich Gallery?

Immich Gallery creates Home Assistant image entities from your Immich library.
Each enabled source gets its own entity and changes automatically at the interval
you choose.

You can display:

- a random image from your entire library;
- a random favorite;
- a separate rotating image for each selected album.

Add the entities to any Home Assistant dashboard using the built-in Picture Entity
card. Immich Gallery can be installed alongside Home Assistant's built-in Immich
integration.

## Features

- Server-side random selection that remains efficient with large libraries
- Repeat avoidance for recently displayed images
- Rotation interval from 1 to 60 minutes
- Album, favorites, and whole-library sources
- Settings that can be changed later without reinstalling
- HTTPS, local HTTP, reverse proxies, and Tailscale addresses
- Immich-generated previews for HEIC, HEIF, RAW, TIFF, and other supported formats
- No telemetry, analytics, cloud relay, or external runtime service

## Requirements

- Home Assistant 2026.4 or newer
- HACS
- A reachable Immich server
- An Immich API key with these permissions:
  - `user.read`
  - `album.read`
  - `asset.read`
  - `asset.view`

A dedicated read-only API key is recommended. Upload, update, delete,
administration, and `asset.download` permissions are not required.

## Installation

### 1. Download from HACS

[![Open your Home Assistant instance and open Immich Gallery in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ofilis&repository=ha-immich-gallery&category=integration)

Alternatively, open HACS, search for **Immich Gallery**, select **Download**, and
restart Home Assistant when requested.

### 2. Add the integration

[![Open your Home Assistant instance and start setting up Immich Gallery.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=immich_gallery)

You can also go to **Settings → Devices & services → Add integration** and search
for **Immich Gallery**.

## Setup

During setup:

1. Enter the address of your Immich server.
2. Enter the dedicated Immich API key.
3. Choose the image sources you want to create.
4. Set the rotation interval and repeat-avoidance history.

Common host formats include:

```text
https://photos.example.com
https://example.com/immich
http://192.168.1.42:2283
http://100.64.12.34:2283
https://immich.example-tailnet.ts.net
```

TLS certificate verification is enabled by default and should normally remain
enabled.

## Add a gallery to a dashboard

Each selected source creates an `image` entity. Choose the entity shown in your
Home Assistant instance and add it with a Picture Entity card:

```yaml
type: picture-entity
entity: image.immich_gallery_random_library
show_name: false
show_state: false
fit_mode: contain
```

Selected albums appear as separate entities named after their albums. Home
Assistant lets you rename both the entity and its entity ID.

## Change settings later

Open:

**Settings → Devices & services → Immich Gallery → Configure**

From there you can change the Immich host, rotate the API key, enable or disable
TLS verification, select albums and other image sources, adjust repeat avoidance,
and change the rotation interval.

## How it works

Immich performs the random search on the server. Immich Gallery requests a small
set of candidates, excludes recently displayed images, and chooses the next image.
This avoids loading an entire large library into Home Assistant.

The displayed image is an Immich-generated preview rather than the original file.
This allows browser-friendly viewing of photos whose originals are stored as HEIC,
HEIF, RAW, TIFF, or other formats supported by Immich.

## Privacy and security

- Images travel directly between Home Assistant and the Immich server you configure.
- The API key is sent only in the `x-api-key` request header.
- Redirects are rejected to prevent credentials from being forwarded to another host.
- Original image files are not requested.
- Credentials, filenames, EXIF data, image bytes, and asset identifiers are excluded
  from diagnostics.
- Image types and response sizes are restricted before content is accepted.

Protect Home Assistant backups and configuration storage because, like other API
credentials, the Immich key is stored in Home Assistant's private configuration.
See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Support and contributing

- Check the [changelog](CHANGELOG.md) for release notes.
- Open a [GitHub issue](https://github.com/ofilis/ha-immich-gallery/issues) for a bug
  or feature request.
- Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.

Never include API keys, private hostnames, album or asset IDs, EXIF data, or private
photos in a public issue.

## License

Immich Gallery is released under the [MIT License](LICENSE).

Logo usage and attribution are documented in [BRANDING.md](BRANDING.md).

Immich Gallery is an independent community project and is not affiliated with or
endorsed by Immich, FUTO, Home Assistant, the Open Home Foundation, or HACS.
Third-party names and marks remain the property of their respective owners.
