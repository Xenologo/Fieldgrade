# Pilot security brief

Fieldgrade is currently offered as a pilot product for controlled evidence handling.

## Storage model

By default, pilot workspaces store files and runtime data in local repository runtime and artifact paths or the equivalent Docker volumes.

Primary locations:

- `termite_fieldpack/runtime`
- `termite_fieldpack/artifacts`
- `mite_ecology/runtime`
- `mite_ecology/artifacts`
- `fieldgrade_ui/runtime`

## What leaves the machine

A local-only pilot can keep evidence on the machine or host where Fieldgrade runs.

If a pilot uses an external AI or API endpoint, prompts, metadata, and selected content may leave the machine according to that endpoint's behaviour. This must be agreed by the pilot user before use.

## API tokens

Fieldgrade uses API tokens to protect the application surface. Pilot operators remain responsible for generating, storing, rotating, and restricting those tokens.

## Deletion and backup

- delete the workspace runtime and artifact paths to remove a pilot workspace
- remove or rotate any API tokens used for that workspace
- delete copied exports and backups separately
- back up runtime and artifact paths before upgrades or migration
- test restore before storing important evidence

## Boundary statement

> Fieldgrade is designed to support controlled evidence handling; pilot users remain responsible for data classification, access control, and compliance obligations.
