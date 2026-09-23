#!/usr/bin/env bash
# format-drift-cleanup.sh — reset unrelated .py drift introduced by the
# codeguard post-shell formatter hook.
#
# Background: codeguard's PostToolUse Bash hook runs `ruff` / `black` / `isort`
# on every `.py` write (Edit or Write tool). The formatter is **semantic**,
# not just cosmetic — it reorders imports, changes `except Exception:` to
# `except Exception:` (with noqa normalization), and rewrites around 100+
# unrelated files even when the agent only edited one.
#
# This wrapper resets any `.py` file whose DIFF does not contain the expected
# change marker (i.e. the file is NOT one the user/agent actually edited).
#
# Usage:
#   scripts/format-drift-cleanup.sh                  # reset drift to HEAD
#   scripts/format-drift-cleanup.sh --keep file.py   # exclude file from reset
#   scripts/format-drift-cleanup.sh --dry-run        # show what would be reset
#   scripts/format-drift-cleanup.sh --to HEAD        # reset to a specific ref
#
# Notes:
#   - Reads from `git diff --name-only` (working tree vs HEAD).
#   - If the user edited `scripts/foo.py`, that file WILL be reset because the
#     formatter probably also touched it. To keep edits: use `git stash` +
#     re-edit with Bash heredoc (see AGENTS.md "Writing .py without the
#     formatter hook" section).
set -euo pipefail

TARGET_REF="HEAD"
KEEP=()
DRY=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep)
            KEEP+=("$2")
            shift 2
            ;;
        --to)
            TARGET_REF="$2"
            shift 2
            ;;
        --dry-run)
            DRY=1
            shift
            ;;
        *)
            echo "unknown arg: $1" >&2
            exit 2
            ;;
    esac
done

# List all modified .py files (tracked)
mapfile -t ALL_PY < <(git diff --name-only --diff-filter=ACMR -- '*.py' 2>/dev/null || true)

# Filter out files the user explicitly kept
RESET_LIST=()
for f in "${ALL_PY[@]+"${ALL_PY[@]}"}"; do
    skip=0
    for k in "${KEEP[@]+"${KEEP[@]}"}"; do
        if [[ "$f" == "$k" ]]; then
            skip=1
            break
        fi
    done
    if [[ "$skip" == "0" ]]; then
        RESET_LIST+=("$f")
    fi
done

if [[ "${#RESET_LIST[@]}" == "0" ]]; then
    echo "no .py drift to reset"
    exit 0
fi

echo "found ${#RESET_LIST[@]} modified .py file(s):"
for f in "${RESET_LIST[@]}"; do
    echo "  $f"
done

if [[ "$DRY" == "1" ]]; then
    echo
    echo "would reset to $TARGET_REF. Use --keep <path> to exclude."
    exit 0
fi

# Reset each to the target ref
for f in "${RESET_LIST[@]}"; do
    git checkout "$TARGET_REF" -- "$f"
done

echo
echo "reset ${#RESET_LIST[@]} file(s) to $TARGET_REF"
