# Fieldgrade v0.9.0-alpha release publication plan

## Status at 2026-05-15

- Local release packet verified under `releases/v0.9.0-alpha/`.
- `releases/v0.9.0-alpha/SHA256SUMS.txt` verifies all staged artifacts and `RELEASE_MANIFEST.json`.
- `RELEASE_MANIFEST.json` artifact byte counts match the staged ZIP files.
- No GitHub Release object exists yet for `v0.9.0-alpha`.
- No GitHub tag exists yet for `v0.9.0-alpha`.

## Release identity

- **Tag name:** `v0.9.0-alpha`
- **Release title:** `Fieldgrade v0.9.0-alpha`
- **Release body source:** `releases/v0.9.0-alpha/RELEASE_BODY.md`
- **Supporting notes:** `RELEASE_NOTES_v0.9.0-alpha.md`
- **Changelog anchor:** `CHANGELOG.md` → `## [0.9.0-alpha] - 2026-05-14`

## Assets to attach

Upload the staged files from `releases/v0.9.0-alpha/`:

1. `fieldgrade-v0.9.0-alpha-source.zip`
2. `fieldgrade-proofops-demo-pack.zip`
3. `fieldgrade-foodqa-sample-pack.zip`
4. `fieldgrade-govai-sample-pack.zip`
5. `SHA256SUMS.txt`
6. `RELEASE_MANIFEST.json`

## Checksum files

- Primary checksum file: `releases/v0.9.0-alpha/SHA256SUMS.txt`
- Manifest checksum entry: `SHA256SUMS.txt` includes `RELEASE_MANIFEST.json`
- Manifest payload: `releases/v0.9.0-alpha/RELEASE_MANIFEST.json`

## Final release body

Use `releases/v0.9.0-alpha/RELEASE_BODY.md` as the GitHub Release body without further edits unless the underlying release packet changes.

## Upload list with verification notes

| File | Verified locally | Manifest entry |
| --- | --- | --- |
| `fieldgrade-v0.9.0-alpha-source.zip` | Yes | Yes |
| `fieldgrade-proofops-demo-pack.zip` | Yes | Yes |
| `fieldgrade-foodqa-sample-pack.zip` | Yes | Yes |
| `fieldgrade-govai-sample-pack.zip` | Yes | Yes |
| `SHA256SUMS.txt` | Yes | n/a |
| `RELEASE_MANIFEST.json` | Yes | n/a |

## Prepared tag notes

Use the following annotation/notes text if the `v0.9.0-alpha` tag is created manually during publication:

> Fieldgrade v0.9.0-alpha is suitable for private evaluation, founder-led setup, and pilot deployments. This alpha adds reproducible lockfiles, release packet materials under `releases/v0.9.0-alpha/`, downloadable demo/sample packs, proof-pack PDFs, pilot intake routes, and launch collateral. It is not yet a self-serve commercial SaaS or certified compliance product.

## Known limitations

- The GitHub Release object has not been published yet.
- The GitHub tag `v0.9.0-alpha` has not been created yet.
- Release assets are only staged in-repo today; they are not attached to a GitHub Release.
- Release publication is still manual; no repository automation currently publishes the release.

## Manual GitHub release steps

1. Create the Git tag `v0.9.0-alpha` on the intended release commit if it is still absent.
2. Open the GitHub Releases page for `Xenologo/Fieldgrade` and start a new release.
3. Select or create tag `v0.9.0-alpha`.
4. Set the release title to `Fieldgrade v0.9.0-alpha`.
5. Paste the contents of `releases/v0.9.0-alpha/RELEASE_BODY.md` into the release body.
6. Upload the six staged files listed above from `releases/v0.9.0-alpha/`.
7. Confirm the attached filenames exactly match the staged artifacts and checksum/manifest files.
8. Publish the release manually.
9. After publication, update `RELEASE_CHECKLIST.md` to mark the GitHub Release publication and asset-attachment checkboxes complete.
