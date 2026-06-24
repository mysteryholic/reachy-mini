#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=0
INCLUDE_BUILD=0
PIP_CACHE=0

for argument in "$@"; do
  case "$argument" in
    --dry-run) DRY_RUN=1 ;;
    --include-build) INCLUDE_BUILD=1 ;;
    --pip-cache) PIP_CACHE=1 ;;
    *)
      echo "Usage: $0 [--dry-run] [--include-build] [--pip-cache]" >&2
      exit 2
      ;;
  esac
done

remove_path() {
  path="$1"
  [ -e "$path" ] || return 0
  echo "$path"
  if [ "$DRY_RUN" -eq 0 ]; then
    rm -rf -- "$path"
  fi
}

find "$ROOT" -type d \( \
  -name "__pycache__" -o \
  -name ".pytest_cache" -o \
  -name ".mypy_cache" -o \
  -name ".ruff_cache" \
\) -prune -print | while IFS= read -r path; do
  remove_path "$path"
done

find "$ROOT" -type f -name "*.pyc" -print | while IFS= read -r path; do
  remove_path "$path"
done

if [ "$INCLUDE_BUILD" -eq 1 ]; then
  remove_path "$ROOT/build"
fi

if [ "$PIP_CACHE" -eq 1 ]; then
  remove_path "${XDG_CACHE_HOME:-$HOME/.cache}/pip"
fi
