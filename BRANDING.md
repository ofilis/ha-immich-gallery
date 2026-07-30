# Branding and trademark notice

The small Immich Gallery integration icon uses the official Immich flower
artwork without an overlay or redraw. It exists only so HACS and Home Assistant
can visually identify the supported service.

The repository intentionally does not include or display an Immich banner,
wide wordmark, screenshot, or other Immich marketing image.

## Official source artwork

The Immich artwork was retrieved from the official
[`immich-app/immich`](https://github.com/immich-app/immich/tree/7e70f90c15466cfd709ceed6442df18b03912716/design)
repository on 30 July 2026, at commit
`7e70f90c15466cfd709ceed6442df18b03912716`:

| Upstream file | SHA-256 |
| --- | --- |
| `design/immich-logo.png` | `fd8c4505dae227ce7d9f5a1dfc98bc761cc78c7ed7ece0efad99cd4a1136e724` |

Immich's own
[Unraid installation guide](https://docs.immich.app/install/unraid/)
also points users to the official `design/immich-logo.png` asset for visual
identification.

## Ownership and non-affiliation

“Immich” and the Immich flower are used nominatively to identify compatibility
with the Immich software. Those names and marks remain the property of their
respective owner and are expressly excluded from this repository's MIT
license.

Immich Gallery is an independent community project and is not affiliated with,
sponsored by, or endorsed by the Immich project, FUTO, Home Assistant, the
Open Home Foundation, or HACS. Do not use the integration icon in a way that
implies official endorsement.

The Immich FAQ discusses notification for integrations under its commercial
guidelines and recommends direct contact for edge-case trademark use. This
repository is a non-commercial, independent compatibility project with a
prominent non-affiliation notice and limited icon use. Any future commercial
use or broader marketing use should first be discussed with Immich:
[Immich FAQ](https://docs.immich.app/FAQ/).

## Included files

- `brand/icon.png`: 256 × 256 official flower, transparent
- `brand/icon@2x.png`: 512 × 512 official flower, transparent

The runtime integration does not download branding from an external server.
Home Assistant serves these local files through its authenticated brands API.
