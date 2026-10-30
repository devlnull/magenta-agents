#!/bin/sh
# Magenta Agents installer for macOS and Linux (also works in Git Bash on Windows).
#
#   curl -fsSL https://raw.githubusercontent.com/devlnull/magenta-agents/main/install.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/devlnull/magenta-agents/main/install.sh | sh -s -- --target opencode --ref v0.5.0
#
# Options (or environment variables):
#   --target claude-code|opencode|codex|gemini   (MAGENTA_TARGET, default claude-code)
#   --ref <branch or tag>                 (MAGENTA_REF, default main)
#   --dir <folder for the source>         (MAGENTA_HOME, default ~/.magenta-agents)
#   --repo <git URL>                      (MAGENTA_REPO)
set -eu

REPO_GIVEN="${MAGENTA_REPO:-}"
REPO="${MAGENTA_REPO:-https://github.com/devlnull/magenta-agents.git}"
REF="${MAGENTA_REF:-main}"
DIR="${MAGENTA_HOME:-$HOME/.magenta-agents}"
TARGET="${MAGENTA_TARGET:-claude-code}"

while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --ref) REF="$2"; shift 2 ;;
    --dir) DIR="$2"; shift 2 ;;
    --repo) REPO="$2"; REPO_GIVEN="$2"; shift 2 ;;
    -h|--help)
      cat <<USAGE
Magenta Agents installer for macOS and Linux (also works in Git Bash on Windows).

Options (or environment variables):
  --target claude-code|opencode|codex|gemini   (MAGENTA_TARGET, default claude-code)
  --ref <branch or tag>                 (MAGENTA_REF, default main)
  --dir <folder for the source>         (MAGENTA_HOME, default ~/.magenta-agents)
  --repo <git URL>                      (MAGENTA_REPO)
USAGE
      exit 0 ;;
    *) echo "magenta: unknown option: $1" >&2; exit 1 ;;
  esac
done

fail() { echo "magenta: $*" >&2; exit 1; }

PY=""
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    PY="$candidate"; break
  fi
done
[ -n "$PY" ] || fail "Python 3.9 or later is necessary. macOS: xcode-select --install (or brew install python). Linux: install python3 with your package manager."
command -v git >/dev/null 2>&1 || fail "git is necessary."

if [ -d "$DIR/.git" ]; then
  echo "magenta: updating $DIR to $REF"
  [ -z "${REPO_GIVEN:-}" ] || git -C "$DIR" remote set-url origin "$REPO"
  git -C "$DIR" fetch --quiet --depth 1 origin "$REF"
  git -C "$DIR" checkout --quiet --force FETCH_HEAD
else
  echo "magenta: downloading $REPO ($REF) to $DIR"
  git clone --quiet --depth 1 --branch "$REF" "$REPO" "$DIR"
fi

"$PY" "$DIR/magenta.py" validate
"$PY" "$DIR/magenta.py" build
"$PY" "$DIR/magenta.py" install --target "$TARGET"

cat <<NEXT

Magenta is installed for $TARGET.
Next steps:
  1. Prepare a repository (one time). For Claude Code, this also adds the hooks that enforce the checks:
       $PY "$DIR/magenta.py" init /path/to/your/repository
  2. Open your tool in the repository and run a task:
       Claude Code, OpenCode, Gemini CLI:  /magenta <your task>
       Codex CLI:                          \$magenta <your task>
     The first time, Magenta asks to run discover-project for the repository.
  3. Approve the checks when Magenta asks. Only you can approve them.
Update later: run this installer again. Remove: $PY "$DIR/magenta.py" uninstall
NEXT
