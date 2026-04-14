#!/bin/sh
# Claude Doctor — Python interpreter auto-detector
# Tries uv run > python3 > python in order.
# Usage: sh run.sh <hook_script_name_without_extension> [args...]
#
# Rationale: Windows typically has `python`, Linux typically `python3`,
# and `uv run python` works everywhere if uv is installed. Hardcoding
# `python3` causes silent failures on Windows (see hookify issue #405).

HOOK_NAME="$1"
shift

if [ -z "$HOOK_NAME" ]; then
  echo '{"systemMessage": "claude-doctor run.sh: hook name missing"}' >&2
  exit 0
fi

HOOK_PATH="${CLAUDE_PLUGIN_ROOT}/hooks/${HOOK_NAME}.py"

if [ ! -f "$HOOK_PATH" ]; then
  echo "{\"systemMessage\": \"claude-doctor: hook script not found: $HOOK_PATH\"}" >&2
  exit 0
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run python "$HOOK_PATH" "$@"
elif command -v python3 >/dev/null 2>&1; then
  exec python3 "$HOOK_PATH" "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$HOOK_PATH" "$@"
else
  echo '{"systemMessage": "claude-doctor: no Python interpreter found (tried uv, python3, python)"}' >&2
  exit 0
fi
