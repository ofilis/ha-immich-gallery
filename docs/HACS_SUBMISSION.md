# HACS default-library submission plan

This checklist covers publication of `ofilis/ha-immich-gallery` and admission
to the default HACS library. It is intentionally separate from installation as
a custom repository.

## 1. Publish a complete public repository

Repository:

```text
https://github.com/ofilis/ha-immich-gallery
```

Required repository settings:

- visibility: public;
- default branch: `main`;
- Issues: enabled;
- description: `Rotating Immich album, favorite, and library images for Home Assistant`;
- suggested topics:

  - `home-assistant`
  - `hacs`
  - `immich`
  - `gallery`
  - `image-entity`
  - `self-hosted`
  - `privacy`

The repository owner must review all files before the first push. No real host,
API key, personal media, album ID, asset ID, or private screenshot may be
present.

## 2. Validate the repository

The repository includes:

- `.github/workflows/validate.yml`
  - HACS validation;
  - Hassfest;
- `.github/workflows/tests.yml`
  - Ruff;
  - Python tests against the supported Home Assistant release range.

Both workflows must pass on `main` with no ignored HACS checks.

Immich Gallery complements the built-in Home Assistant Immich integration with
rotating `image` entities. It uses the independent `immich_gallery` domain; it
is neither an override nor an alpha/beta distribution of the core `immich`
integration.

The following must also be confirmed:

- `manifest.json` has the correct domain, name, version, documentation,
  issue tracker, and `@ofilis` code owner;
- `hacs.json` has the display name and minimum Home Assistant version;
- `custom_components/immich_gallery/brand/icon.png` exists;
- installation works from HACS as a custom repository;
- setup, Configure, unload, reload, and removal work on a clean Home Assistant
  test instance.

## 3. Capture public-safe screenshots

After the first clean test installation, add redacted screenshots under
`docs/images/`:

1. HACS repository page showing the project icon;
2. Home Assistant Add Integration result for **Immich Gallery**;
3. initial host/API-key form with only example values;
4. Configure form showing host, TLS, sources, recent-history window, and
   refresh interval;
5. Devices & services entry showing the project icon;
6. a dashboard card using non-sensitive sample media.

Do not use a private hostname, Tailscale IP, real API key, personal album name,
person name, filename, or family photo.

## 4. Create a full GitHub release

After validation succeeds:

1. Confirm `manifest.json` contains the release version.
2. Update `CHANGELOG.md`.
3. Add a curated announcement under `docs/releases/`.
4. Follow the exact checks and command sequence in
   [`docs/RELEASING.md`](RELEASING.md).
5. Create and push a version tag such as `v0.1.0`.
6. Publish a full GitHub Release from that tag using the curated announcement.
7. Confirm HACS shows the announcement and can install the release as a custom
   repository.

A tag without a GitHub Release is not sufficient for default-library
submission.

## 5. Branding requirement

Home Assistant 2026.3 and newer supports brand images inside:

```text
custom_components/immich_gallery/brand/
```

The current Home Assistant brands repository describes
`custom_integrations/` as a legacy path, while the current HACS integration
documentation requires a local `brand` directory with at least `icon.png`.

The current HACS default-inclusion check first looks for this local brand
directory and only falls back to `home-assistant/brands` when it is absent.
The bundled local files therefore satisfy the documented route; do not open a
duplicate legacy brands pull request.

Before the first public release, send Immich a short notification describing
the independent integration and its use of the official flower for
HACS/Home Assistant identification. Include the repository URL and the
non-affiliation statement. The repository does not use an Immich banner or
wide wordmark. The Immich FAQ says integrations for other platforms are
typically approved when proper notification is given. Record and follow any
brand-use direction received.

## 6. Submit to `hacs/default`

Only the repository owner or a major contributor may submit.

1. Fork [`hacs/default`](https://github.com/hacs/default) under the personal
   account.
2. Create a new branch from the current `master` branch.
3. Add this entry alphabetically to the `integration` JSON list:

   ```json
   "ofilis/ha-immich-gallery"
   ```

4. Open a pull request back to `hacs/default:master`.
5. Allow maintainers to edit the pull request.
6. Complete every item in the HACS pull-request template accurately.
7. Resolve all automated checks before requesting review.

Do not submit from an organization-owned fork and do not use the fork's
`master` branch for the change.

## 7. Maintain the repository while waiting

HACS warns that new default-repository reviews can take months.

During the review period:

- keep the latest GitHub Release installable;
- keep Issues enabled and answer actionable reports;
- keep HACS, Hassfest, and tests green;
- update Immich API compatibility when stable endpoints change;
- do not archive the repository;
- do not rename the repository or integration domain;
- avoid breaking changes before the first default-library review.

After the pull request is merged, HACS includes the repository in its next
scheduled scan.

## Official references

- [HACS general publishing requirements](https://www.hacs.xyz/docs/publish/start/)
- [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/)
- [HACS validation action](https://hacs.xyz/docs/publish/action/)
- [HACS default-library inclusion](https://hacs.xyz/docs/publish/include/)
- [Home Assistant local brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/)
- [Home Assistant brands repository](https://github.com/home-assistant/brands)
