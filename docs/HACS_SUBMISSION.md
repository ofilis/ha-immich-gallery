# HACS default-library submission

This document tracks admission of `ofilis/ha-immich-gallery` to the default
HACS library. Default inclusion is separate from installation as a custom
repository.

## Verified readiness

The following baseline was verified on 30 July 2026:

| Requirement | Status | Evidence |
| --- | --- | --- |
| Public GitHub repository | Ready | [`ofilis/ha-immich-gallery`](https://github.com/ofilis/ha-immich-gallery) |
| Repository description, topics, and Issues | Ready | Public repository metadata |
| One integration under `custom_components` | Ready | `custom_components/immich_gallery` |
| Required `manifest.json` fields | Ready | Domain, name, version, documentation, issue tracker, and code owner are present |
| Required `hacs.json` name | Ready | `Immich Gallery` |
| Local integration brand | Ready | `brand/icon.png` and `brand/icon@2x.png` |
| HACS validation without ignored checks | Passing | [HACS job](https://github.com/ofilis/ha-immich-gallery/actions/runs/30555786689/job/90915756656) |
| Hassfest | Passing | [Hassfest job](https://github.com/ofilis/ha-immich-gallery/actions/runs/30555786689/job/90915756736) |
| Full release after validation | Ready | [`v0.1.0`](https://github.com/ofilis/ha-immich-gallery/releases/tag/v0.1.0) |
| Custom-repository installation | Verified | Installed successfully in Home Assistant |
| Eligible submitter | Ready | `@ofilis` owns the repository |

Immich Gallery complements the built-in Home Assistant Immich integration with
rotating `image` entities. It uses the independent `immich_gallery` domain; it
is neither an override nor an alpha/beta distribution of the core `immich`
integration.

The integration is global, so a country key is not appropriate in `hacs.json`.

## Repository safeguards

The repository includes:

- `.github/workflows/validate.yml`
  - HACS validation without an `ignore` key;
  - Hassfest;
- `.github/workflows/tests.yml`
  - Ruff linting and formatting;
  - Python tests;
- `tests/test_hacs_metadata.py`
  - one-integration repository structure;
  - required HACS and Home Assistant manifest metadata;
  - local PNG icon presence and exact dimensions;
  - enabled HACS and Hassfest workflow checks.

Before every submission or release, confirm that no real host, API key,
personal media, album ID, asset ID, or private screenshot is present.

## Images and branding

Home Assistant 2026.3 and newer supports local brand images inside:

```text
custom_components/immich_gallery/brand/
```

Local assets take precedence in Home Assistant. HACS default-inclusion checks
also accept this directory and only fall back to the legacy
`home-assistant/brands` repository when it is absent.

No README screenshot is required for an integration. HACS applies its README
image check only to plugins and themes. Immich Gallery therefore does not add
a banner, library screenshot, personal photo, or other marketing image. Only
the small local integration icons required for service identification are
included.

HACS 2.0.5 can still show an icon placeholder in its own repository list and
update dialog because those views do not yet consume Home Assistant's local
brand API. This does not mean the packaged icon is missing and does not block
default-library admission. See [HACS icon behavior](HACS_ICON.md) for the
root-cause analysis and upstream fixes.

Immich's FAQ discusses notification for plugin integrations in its commercial
guidelines and recommends direct contact for edge-case trademark use. Immich
Gallery is a non-commercial, independent compatibility project with a
prominent non-affiliation statement and limited icon use. Any future commercial
use or broader marketing use should first be discussed with Immich. Trademark
correspondence is separate from the HACS admission requirements.

## Release ordering

HACS requires a full GitHub Release created after successful HACS and Hassfest
validation. A tag alone is insufficient.

The verified `v0.1.0` release satisfies that order for commit `f5e19a6`. If
anything is pushed to `main` before the default-library pull request:

1. update the manifest version, changelog, and curated release notes;
2. push the release-preparation commit;
3. wait for Tests, HACS, and Hassfest to pass on that exact commit;
4. create the version tag and full GitHub Release afterward;
5. use the new release and action links in the HACS pull request.

Follow [`docs/RELEASING.md`](RELEASING.md) for the complete release procedure.

## Submit to `hacs/default`

Only the repository owner or a major contributor may submit.

1. Fork [`hacs/default`](https://github.com/hacs/default) to the personal
   `ofilis` account.
2. Create a new branch from the current upstream `master` branch. Do not make
   the change directly on the fork's `master` branch.
3. Add this entry alphabetically to the `integration` JSON array:

   ```json
   "ofilis/ha-immich-gallery"
   ```

   At the time of verification, its exact position is:

   ```json
   "ofalvai/home-assistant-candy",
   "ofilis/ha-immich-gallery",
   "ogerardin/ha-cfl-commute",
   ```

4. Open a pull request to `hacs/default:master`.
5. Allow maintainers to edit the pull request.
6. Complete every item in the current pull-request template accurately.
7. Link the current full release and the successful HACS and Hassfest jobs.
8. Do not request reviews. The HACS template explicitly warns that doing so
   will close the pull request.

The submission changes only the `integration` JSON file in `hacs/default`.
It does not add this project's icon or any screenshots to that repository.

## Current pull-request template

Use the latest upstream template when the pull request is opened. Its required
content was:

```markdown
## Checklist

- [x] I've read the publishing documentation.
- [x] I've added the HACS action to my repository.
- [x] (For integrations only) I've added the hassfest action to my repository.
- [x] The actions are passing without any disabled checks in my repository.
- [x] I've added a link to the action run on my repository below.
- [x] I've created a new release after the validation actions succeeded.

## Links

Link to current release: <RELEASE_URL>
Link to successful HACS action (without the `ignore` key): <HACS_JOB_URL>
Link to successful hassfest action (if integration): <HASSFEST_JOB_URL>
```

Replace all three placeholders with the final post-change links. Do not submit
the older `v0.1.0` links if a newer commit has been pushed.

## After submission

HACS warns that new default-repository reviews can take months. During that
period:

- keep the latest GitHub Release installable;
- keep Issues enabled and answer actionable reports;
- keep HACS, Hassfest, and tests green;
- update Immich API compatibility when stable endpoints change;
- do not archive or rename the repository;
- do not rename the integration domain;
- avoid breaking changes before the first default-library review.

After the pull request is merged, HACS includes the repository in its next
scheduled scan. It then becomes searchable without adding it as a custom
repository.

## Official references

- [HACS general publishing requirements](https://www.hacs.xyz/docs/publish/start/)
- [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/)
- [HACS validation action](https://hacs.xyz/docs/publish/action/)
- [HACS default-library inclusion](https://www.hacs.xyz/docs/publish/include/)
- [Home Assistant local brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/)
- [HACS default repository](https://github.com/hacs/default)
