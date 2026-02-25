#!/usr/bin/env bash
# Install git hooks from scripts/hooks/ into .git/hooks/.
#
# Usage:
#   bash scripts/install_hooks.sh
#
# Hooks installed:
#   pre-push  — runs pytest with coverage check before every push
#
# Exit codes:
#   0 = all hooks installed successfully
#   1 = must be run from repository root or git repo not found

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOOKS_SRC="${SCRIPT_DIR}/hooks"
HOOKS_DST="${REPO_ROOT}/.git/hooks"

# Verify we're inside a git repo
if [[ ! -d "${HOOKS_DST}" ]]; then
    echo "Error: .git/hooks not found — run this script from the repository root."
    exit 1
fi

installed=0
for src in "${HOOKS_SRC}"/*; do
    hook_name="$(basename "${src}")"
    dst="${HOOKS_DST}/${hook_name}"

    if [[ -e "${dst}" && ! -L "${dst}" ]]; then
        echo "Backing up existing ${hook_name} → ${dst}.bak"
        cp "${dst}" "${dst}.bak"
    fi

    cp "${src}" "${dst}"
    chmod +x "${dst}"
    echo "✅ Installed ${hook_name} → .git/hooks/${hook_name}"
    installed=$((installed + 1))
done

echo ""
echo "Installed ${installed} hook(s). Run 'git push' to verify."
