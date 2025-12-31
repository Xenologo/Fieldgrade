# Backups + restore drill (single-host v0)

Single-host v0 keeps state in Docker volumes:

- termite runtime + artifacts
- mite_ecology runtime + artifacts
- fieldgrade_ui runtime
- Caddy cert/state

This guide provides a minimal, repeatable backup + restore flow.

## Backup (recommended nightly)

This repo includes a VPS helper script:

- `scripts/vps_backup_volumes.sh`

It archives **all** Docker volumes labeled with:

- `com.docker.compose.project=<project>`

### One-time setup

1) Choose a predictable compose project name on the VPS.

Recommended: export `COMPOSE_PROJECT_NAME=fg_next` in your shell or set it in your systemd env file (below).

2) Create a backup destination:

- `sudo mkdir -p /var/backups/fieldgrade`
- `sudo chmod 700 /var/backups/fieldgrade`

### Manual backup run

From the `fg_next/` directory on the VPS:

- Hot backup (no downtime; may be inconsistent for SQLite under write load):
  - `./scripts/vps_backup_volumes.sh --backup-dir /var/backups/fieldgrade --keep-days 14`

- Cold backup (recommended; stops and restarts the stack):
  - `./scripts/vps_backup_volumes.sh --backup-dir /var/backups/fieldgrade --keep-days 14 --compose-files "compose.yaml compose.production.yaml" --stop-stack --restart-stack`

Each run produces a directory like:

- `/var/backups/fieldgrade/volumes_<project>_<timestamp>/`

Including:

- one `*.tar.gz` per volume
- `VOLUMES.txt`
- `SHA256SUMS.txt`

## systemd timer (nightly)

Unit files are provided in:

- `scripts/systemd/fieldgrade-volumes-backup.service`
- `scripts/systemd/fieldgrade-volumes-backup.timer`

### Install

On the VPS:

- `sudo install -D -m 0644 scripts/systemd/fieldgrade-volumes-backup.service /etc/systemd/system/fieldgrade-volumes-backup.service`
- `sudo install -D -m 0644 scripts/systemd/fieldgrade-volumes-backup.timer /etc/systemd/system/fieldgrade-volumes-backup.timer`

Optional env overrides (recommended):

- `sudo install -D -m 0600 /dev/null /etc/fieldgrade/backup.env`
- Edit `/etc/fieldgrade/backup.env`:
  - `COMPOSE_PROJECT_NAME=fg_next`
  - `BACKUP_DIR=/var/backups/fieldgrade`
  - `KEEP_DAYS=14`

Enable timer:

- `sudo systemctl daemon-reload`
- `sudo systemctl enable --now fieldgrade-volumes-backup.timer`

Check status/logs:

- `systemctl list-timers --all | grep fieldgrade`
- `sudo journalctl -u fieldgrade-volumes-backup.service -n 200 --no-pager`

## Restore drill (practice)

Do this on a staging VPS or during a maintenance window.

1) Pick a backup directory (example):

- `/var/backups/fieldgrade/volumes_fg_next_20251231T033000Z/`

2) Stop the stack:

- `docker compose -p fg_next -f compose.yaml -f compose.production.yaml down`

3) Restore volumes:

For each volume tarball in the backup directory:

- Ensure the volume exists:
  - `docker volume create <volume_name>`
- Restore into it:
  - `docker run --rm -v <volume_name>:/v -v /var/backups/fieldgrade/volumes_fg_next_...:/in alpine:3.20 sh -lc "cd /v && rm -rf ./* && tar -xzf /in/<volume_name>.tar.gz"`

4) Bring stack up:

- `docker compose -p fg_next -f compose.yaml -f compose.production.yaml up -d --build`

5) Verify externally:

- `https://$FIELDGRADE_DOMAIN/readyz`

Notes:
- If you change `COMPOSE_PROJECT_NAME`, your volume names will change.
- For Phase 3 (managed Postgres), switch backups to Postgres-native snapshots/PITR and treat volumes as cache/artifacts.
