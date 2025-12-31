#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  vps_backup_volumes.sh [options]

Back up all Docker volumes labeled with com.docker.compose.project=<project>.
This captures Fieldgrade state (runtime DBs, artifacts, and Caddy state) in
one timestamped directory.

Options:
  --project NAME             Compose project name (default: $COMPOSE_PROJECT_NAME or basename of CWD)
  --backup-dir PATH          Where backups are written (default: /var/backups/fieldgrade)
  --keep-days N              Delete backup directories older than N days (default: 14)
  --compose-files "a b c"     Space-separated compose files for stop/restart actions
  --stop-stack               Stop the compose stack before backing up (safer for SQLite)
  --restart-stack            Bring the compose stack back up after backup (implies --compose-files)
  -h, --help                 Show help

Example (recommended nightly "cold" backup):
  cd /opt/fieldgrade/fg_next
  COMPOSE_PROJECT_NAME=fg_next \
    ./scripts/vps_backup_volumes.sh \
      --backup-dir /var/backups/fieldgrade \
      --compose-files "compose.yaml compose.production.yaml" \
      --stop-stack --restart-stack
EOF
}

project="${COMPOSE_PROJECT_NAME:-$(basename "$(pwd)")}" 
backup_dir="/var/backups/fieldgrade"
keep_days="14"
compose_files=""
stop_stack="0"
restart_stack="0"

while [ $# -gt 0 ]; do
  case "$1" in
    --project)
      project="$2"; shift 2 ;;
    --backup-dir)
      backup_dir="$2"; shift 2 ;;
    --keep-days)
      keep_days="$2"; shift 2 ;;
    --compose-files)
      compose_files="$2"; shift 2 ;;
    --stop-stack)
      stop_stack="1"; shift 1 ;;
    --restart-stack)
      restart_stack="1"; shift 1 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [ "$restart_stack" = "1" ] && [ -z "${compose_files}" ]; then
  echo "--restart-stack requires --compose-files" >&2
  exit 2
fi

mkdir -p "$backup_dir"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
out_dir="${backup_dir%/}/volumes_${project}_${ts}"
mkdir -p "$out_dir"

compose_args=()
if [ -n "${compose_files}" ]; then
  # shellcheck disable=SC2206
  files=( ${compose_files} )
  for f in "${files[@]}"; do
    compose_args+=( -f "$f" )
  done
fi

if [ "$stop_stack" = "1" ]; then
  if [ ${#compose_args[@]} -eq 0 ]; then
    echo "--stop-stack requires --compose-files" >&2
    exit 2
  fi
  echo "[backup] stopping compose stack (project=${project})"
  docker compose -p "$project" "${compose_args[@]}" stop
fi

echo "[backup] enumerating volumes for compose project: ${project}"
mapfile -t volumes < <(docker volume ls -q --filter "label=com.docker.compose.project=${project}" | sort)

if [ "${#volumes[@]}" -eq 0 ]; then
  echo "[backup] no volumes found with label com.docker.compose.project=${project}" >&2
  echo "[backup] tip: set --project to your compose project name" >&2
  exit 1
fi

echo "[backup] writing to: ${out_dir}"
printf '%s\n' "${volumes[@]}" > "${out_dir}/VOLUMES.txt"

for v in "${volumes[@]}"; do
  out_file="${out_dir}/${v}.tar.gz"
  echo "[backup] volume: ${v} -> ${out_file}"
  docker run --rm \
    -v "${v}:/v:ro" \
    -v "${out_dir}:/out" \
    alpine:3.20 \
    sh -lc "cd /v && tar -czf '/out/$(basename "${out_file}")' ."
done

# Basic integrity check
( cd "$out_dir" && sha256sum *.tar.gz > SHA256SUMS.txt )

# Cleanup old backups
if [ -n "${keep_days}" ] && [ "$keep_days" -ge 1 ] 2>/dev/null; then
  echo "[backup] pruning backups older than ${keep_days} days in ${backup_dir}"
  find "$backup_dir" -maxdepth 1 -type d -name "volumes_${project}_*" -mtime "+${keep_days}" -print0 | xargs -0r rm -rf
fi

if [ "$restart_stack" = "1" ]; then
  echo "[backup] restarting compose stack (project=${project})"
  docker compose -p "$project" "${compose_args[@]}" up -d
fi

echo "[backup] done"
