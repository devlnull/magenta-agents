#!/bin/sh
# Magenta guard launcher for the team plugin. It finds Python 3.9+ on macOS, Linux, and
# Windows (Claude Code runs hooks in Git Bash there), then runs guard.py with the same input.
dir=$(dirname "$0")
for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1 &&
     "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    exec "$py" "$dir/guard.py" "$@"
  fi
done
# No usable Python. In --auto mode, let sessions that are not Magenta agents continue.
input=$(cat)
if [ "${1:-}" = "--auto" ]; then
  case "$input" in
    *'"agent_type":"magenta'*|*'"agent_type": "magenta'*) ;;
    *) exit 0 ;;
  esac
fi
echo "Magenta guard: blocked, because Python 3.9 or later is not installed. Install Python to use the Magenta agents." >&2
exit 2
