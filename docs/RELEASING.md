# Release process

HACS displays release notes from the body of a full GitHub Release. A Git tag
on its own is not sufficient.

## Prepare the release

1. Choose the next semantic version.
2. Set the same version in
   `custom_components/immich_gallery/manifest.json`.
3. Move completed entries from `Unreleased` into a dated version section in
   `CHANGELOG.md`.
4. Add a curated announcement at `docs/releases/vX.Y.Z.md`.
5. Run:

   ```bash
   ruff check .
   ruff format --check .
   python -m pytest
   ```

6. Merge the release preparation through a pull request.
7. Confirm Tests, HACS, and Hassfest pass on `main`.

## Publish the release

From an up-to-date and clean `main` branch:

```bash
git tag -a vX.Y.Z -m "Immich Gallery vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z \
  --repo ofilis/ha-immich-gallery \
  --title "Immich Gallery vX.Y.Z" \
  --notes-file docs/releases/vX.Y.Z.md \
  --verify-tag
```

The release must remain a normal published release, not a draft or prerelease,
unless it is intentionally being distributed as a beta.

## Verify HACS

1. In HACS, open Immich Gallery and select **Update information**.
2. Confirm the remote version is `vX.Y.Z`.
3. Confirm **Read release announcement** displays the curated release body.
4. Install the update and restart Home Assistant.
5. Confirm the installed version and integration behavior.

Do not publish a release if the tag, manifest version, changelog version, or
release-note filename disagree.
