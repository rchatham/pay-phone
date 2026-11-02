#!/bin/bash
# =============================================================================
# Print the rsync filter arguments used by scripts/deploy_to_pi.sh
# =============================================================================
# One argument per line, in the order rsync must receive them:
#
#   1. --filter=. scripts/deploy_protected_paths.rules
#      Pi-side state (BIOS config, caller recordings) that must survive
#      `rsync --delete`. Edit that file to protect more paths.
#
#   2. --include rules for every top-level directory under plugins/ and
#      audio_files/ that is tracked in git, followed by
#      --exclude=/plugins/* and --exclude=/audio_files/*/
#      so that only in-repo plugins and audio directories are synced. Anything
#      else there on the Pi, such as a theme pack installed with
#      `install.py --copy` (plugins/<pack>/, audio_files/<pack>/), is left
#      untouched, and local plugin symlinks are not shipped as dangling links.
#
# tests/unit/test_deploy_filters.py runs these arguments against a local rsync
# to prove the protected paths survive a deploy.
#
# Usage:
#   scripts/deploy_rsync_filters.sh            # from anywhere inside the repo
# =============================================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
RULES_FILE="$SCRIPT_DIR/deploy_protected_paths.rules"

if [ ! -f "$RULES_FILE" ]; then
    echo "ERROR: missing $RULES_FILE" >&2
    exit 1
fi

# 1. Protected Pi-side state (must come first so it beats the includes below).
echo "--filter=. $RULES_FILE"

# 2. Only tracked plugin / audio directories are synced.
TRACKED_DIRS=$(cd "$PROJECT_ROOT" && git ls-files plugins audio_files \
    | awk -F/ 'NF > 2 { print $1 "/" $2 }' | sort -u)

if [ -z "$TRACKED_DIRS" ]; then
    echo "ERROR: git ls-files found no tracked plugins/ or audio_files/ directories" >&2
    exit 1
fi

for dir in $TRACKED_DIRS; do
    echo "--include=/$dir/"
    echo "--include=/$dir/**"
done

echo "--exclude=/plugins/*"
echo "--exclude=/audio_files/*/"
