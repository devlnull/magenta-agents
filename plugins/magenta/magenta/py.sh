#!/bin/sh
# Magenta launcher: run a Magenta Python script with Python 3.9+ on macOS, Linux, and Windows (Git Bash).
# Usage: py.sh [--fail-open] <script.py> [arguments]
# --fail-open: without Python, exit 0 so that the session can continue (for hooks).
dir=$(dirname "$0")
open=0
if [ "${1:-}" = "--fail-open" ]; then
  open=1
  shift
fi
script=$1
shift
if [ ! -f "$dir/$script" ]; then
  echo "Magenta: $dir/$script does not exist. Install Magenta again." >&2
  if [ "$open" = 1 ]; then exit 0; fi
  exit 4
fi
for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1 &&
     "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    exec "$py" "$dir/$script" "$@"
  fi
done
echo "Magenta: Python 3.9 or later is not installed, so $script cannot run. Install Python 3." >&2
if [ "$open" = 1 ]; then
  exit 0
fi
exit 4
