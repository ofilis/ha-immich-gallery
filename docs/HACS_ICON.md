# HACS icon behavior

Immich Gallery includes valid local brand assets:

```text
custom_components/immich_gallery/brand/icon.png
custom_components/immich_gallery/brand/icon@2x.png
```

Home Assistant correctly displays these assets on the integration and device
pages. HACS 2.0.5 can nevertheless show **Icon not available** in its
repository list and update dialog.

## Root cause

Home Assistant 2026.3 introduced local brand assets for custom integrations.
It serves them through its authenticated same-origin brands API:

```text
/api/brands/integration/{domain}/{image}
```

HACS 2.0.5 predates full support for that route in its own user interface. The
repository dashboard uses the legacy frontend brands helper, and its update
entity independently builds the integration icon URL from the legacy public
Home Assistant brands CDN:

```text
https://brands.home-assistant.io/_/{domain}/icon.png
```

For Immich Gallery, that becomes:

```text
https://brands.home-assistant.io/_/immich_gallery/icon.png
```

The local icon in this repository is not published at that legacy CDN URL, so
HACS receives a placeholder. A GitHub release cannot change this lookup path.

The behavior is tracked upstream:

- [`hacs/integration#5223`](https://github.com/hacs/integration/issues/5223)
  describes missing inline custom-integration brands;
- [`hacs/integration#5402`](https://github.com/hacs/integration/issues/5402)
  confirms the behavior on current Home Assistant and HACS versions;
- [`hacs/integration#5388`](https://github.com/hacs/integration/pull/5388)
  adds a repository brand-icon endpoint;
- [`hacs/frontend#945`](https://github.com/hacs/frontend/pull/945) switches the
  HACS repository dashboard to that endpoint;
- [`hacs/integration#5339`](https://github.com/hacs/integration/pull/5339) and
  [`hacs/integration#5228`](https://github.com/hacs/integration/pull/5228)
  explore the separate update-entity change.

The repository-list backend and frontend changes must both reach a released
HACS version before the store view can display the icon. The Home Assistant
update dialog also needs its separate update-entity change. These pull requests
are currently open and are not part of HACS 2.0.5.

## Why the integration is configured correctly

The current official requirements say:

- custom integrations may package a local `brand/` directory;
- local assets take precedence in Home Assistant;
- an integration submitted to the default HACS library must provide at least
  `brand/icon.png`;
- HACS default-inclusion validation checks the local brand directory before
  consulting the legacy Home Assistant brands repository.

Immich Gallery meets those requirements. The Home Assistant integration page
successfully rendering the flower confirms that the installed component
contains a readable local asset.

Automated tests additionally verify:

- PNG signatures;
- a 256 × 256 standard icon;
- a 512 × 512 high-density icon;
- the expected `immich_gallery` integration path.

## Unsupported workarounds

The following do not fix the HACS 2.0.5 lookup:

- adding an arbitrary icon URL to `hacs.json`;
- copying the icon to the repository root;
- adding README screenshots or a banner;
- publishing another GitHub release without a HACS code change;
- opening a new legacy custom-integration brand pull request.

There is no supported repository manifest field that overrides the HACS icon
URL. Adding non-standard metadata would not make HACS consume the local file.

## Resolution

Repository-side work is complete: retain the local icons and their regression
tests. Track the upstream HACS issues and pull requests. Once a HACS release
includes the relevant store and update-entity changes, update HACS and refresh
repository information.

Default-library admission can proceed independently. The HACS inclusion check
accepts the local brand directory, so this display bug is not a submission
blocker and does not require publishing personal images.

## References

- [Home Assistant local brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/)
- [HACS integration brand requirements](https://www.hacs.xyz/docs/publish/integration/#brand-assets)
- [HACS default-inclusion brand check](https://www.hacs.xyz/docs/publish/include/#check-brands)
- [HACS 2.0.5 update entity source](https://github.com/hacs/integration/blob/2.0.5/custom_components/hacs/update.py)
- [HACS 2.0.5 release](https://github.com/hacs/integration/releases/tag/2.0.5)
