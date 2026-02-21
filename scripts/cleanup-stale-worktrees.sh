#!/usr/bin/env bash
#
# Clean up stale git worktrees for closed/merged GitHub issues.
#
# Detects stale worktrees via two independent signals:
#   1. Associated GitHub issue is closed (CLOSED state)
#   2. Branch is merged into main
#
# Usage:
#   ./scripts/cleanup-stale-worktrees.sh [OPTIONS]
#
# Options:
#   --force           Auto-cleanup without prompting (non-interactive)
#   --log-file PATH   Override default log file path
#   --dry-run         Show what would be cleaned without making changes
#   --help            Show this help message
#
# Logs cleanup actions to ~/.cache/scylla/worktree-cleanup.log by default.

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_LOG_FILE="${HOME}/.cache/scylla/worktree-cleanup.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
log_skip()  { echo -e "${BLUE}[SKIP]${NC}  $1"; }

# Append a timestamped entry to the log file.
# Arguments:
#   $1  action  (REMOVED | SKIPPED | DRY_RUN)
#   $2  path
#   $3  branch
#   $4  issue   (number or "none")
log_action() {
    local action="$1" path="$2" branch="$3" issue="$4"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "${timestamp} ${action} path=${path} branch=${branch} issue=${issue}" >> "$LOG_FILE"
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
FORCE=false
DRY_RUN=false
LOG_FILE="$DEFAULT_LOG_FILE"

usage() {
    sed -n '/^# Usage:/,/^[^#]/{ /^#/{ s/^# \{0,1\}//; p }; /^[^#]/q }' "$0"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)    FORCE=true;        shift ;;
        --dry-run)  DRY_RUN=true;      shift ;;
        --log-file) LOG_FILE="$2";     shift 2 ;;
        --help|-h)  usage; exit 0 ;;
        *) log_error "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Detect main branch dynamically
# ---------------------------------------------------------------------------
get_main_branch() {
    git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null \
        | sed 's@^refs/remotes/origin/@@' \
        || echo "main"
}

# ---------------------------------------------------------------------------
# Parse `git worktree list --porcelain` into parallel arrays.
# Outputs lines of the form: <path> <branch>
# Skips bare worktrees and worktrees with detached HEAD.
# ---------------------------------------------------------------------------
list_worktrees() {
    local path="" branch=""
    while IFS= read -r line; do
        if [[ $line =~ ^worktree[[:space:]](.+)$ ]]; then
            path="${BASH_REMATCH[1]}"
            branch=""
        elif [[ $line =~ ^branch[[:space:]]refs/heads/(.+)$ ]]; then
            branch="${BASH_REMATCH[1]}"
        elif [[ -z "$line" ]]; then
            # End of stanza — emit if we have both fields
            if [[ -n "$path" && -n "$branch" ]]; then
                echo "$path $branch"
            fi
            path=""
            branch=""
        fi
    done < <(git worktree list --porcelain; echo "")
}

# ---------------------------------------------------------------------------
# Check if a branch is merged into main.
# Arguments: $1 branch, $2 main_branch
# ---------------------------------------------------------------------------
is_merged() {
    local branch="$1" main_branch="$2"
    git branch --merged "$main_branch" 2>/dev/null | grep -qE "(^|\s)${branch}$"
}

# ---------------------------------------------------------------------------
# Check if a GitHub issue is closed.
# Arguments: $1 issue_number
# Returns 0 if closed, 1 otherwise.
# Echos the issue state on stdout for the caller.
# ---------------------------------------------------------------------------
issue_state() {
    local issue="$1"
    gh issue view "$issue" --json state --jq '.state' 2>/dev/null || echo "UNKNOWN"
}

# ---------------------------------------------------------------------------
# Safety: check for uncommitted changes in a worktree.
# Arguments: $1 worktree_path
# Returns 0 if dirty, 1 if clean.
# ---------------------------------------------------------------------------
is_dirty() {
    local path="$1"
    [[ -n "$(git -C "$path" status --porcelain 2>/dev/null)" ]]
}

# ---------------------------------------------------------------------------
# Safety: check if a worktree is locked.
# Arguments: $1 worktree_path
# ---------------------------------------------------------------------------
is_locked() {
    local path="$1"
    git worktree list --porcelain 2>/dev/null \
        | grep -A 3 "^worktree ${path}$" \
        | grep -q "^locked"
}

# ---------------------------------------------------------------------------
# Remove a worktree and optionally delete its branch.
# Arguments: $1 path, $2 branch, $3 issue
# ---------------------------------------------------------------------------
remove_worktree() {
    local path="$1" branch="$2" issue="$3"

    if $DRY_RUN; then
        log_info "[DRY-RUN] Would remove: ${path} (branch: ${branch}, issue: #${issue})"
        log_action "DRY_RUN" "$path" "$branch" "$issue"
        return 0
    fi

    if git worktree remove "$path" 2>/dev/null; then
        log_info "Removed worktree: ${path}"
        # Best-effort branch deletion (may already be gone)
        if git branch -d "$branch" 2>/dev/null; then
            log_info "Deleted branch: ${branch}"
        fi
        log_action "REMOVED" "$path" "$branch" "$issue"
    else
        log_warn "git worktree remove failed for ${path} — try: git worktree remove --force ${path}"
        log_action "SKIPPED" "$path" "$branch" "$issue"
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local main_branch
    main_branch=$(get_main_branch)
    local root_dir
    root_dir=$(git rev-parse --show-toplevel)

    local stale_count=0 cleaned_count=0 skipped_count=0

    echo "Scanning worktrees (main branch: ${main_branch})..."
    echo ""

    while IFS=' ' read -r wt_path wt_branch; do
        # Skip the main worktree
        if [[ "$wt_path" == "$root_dir" ]]; then
            continue
        fi

        # Extract leading issue number from branch name (e.g. "736-description" → "736")
        local issue_number=""
        issue_number=$(echo "$wt_branch" | grep -oP '^\d+' || true)

        # Determine staleness: issue closed OR branch merged
        local is_stale=false reason=""

        if [[ -n "$issue_number" ]]; then
            local state
            state=$(issue_state "$issue_number")
            if [[ "$state" == "CLOSED" ]]; then
                is_stale=true
                reason="issue #${issue_number} is CLOSED"
            fi
        fi

        if ! $is_stale && is_merged "$wt_branch" "$main_branch"; then
            is_stale=true
            reason="branch merged into ${main_branch}"
        fi

        if ! $is_stale; then
            continue
        fi

        stale_count=$((stale_count + 1))
        echo "Stale worktree found:"
        echo "  Path:   ${wt_path}"
        echo "  Branch: ${wt_branch}"
        echo "  Reason: ${reason}"

        # Safety: skip dirty worktrees
        if is_dirty "$wt_path"; then
            log_warn "Skipping (uncommitted changes present): ${wt_path}"
            log_action "SKIPPED" "$wt_path" "$wt_branch" "${issue_number:-none}"
            skipped_count=$((skipped_count + 1))
            echo ""
            continue
        fi

        # Safety: skip locked worktrees
        if is_locked "$wt_path"; then
            log_warn "Skipping (worktree is locked): ${wt_path}"
            log_action "SKIPPED" "$wt_path" "$wt_branch" "${issue_number:-none}"
            skipped_count=$((skipped_count + 1))
            echo ""
            continue
        fi

        if $FORCE || $DRY_RUN; then
            remove_worktree "$wt_path" "$wt_branch" "${issue_number:-none}"
            if ! $DRY_RUN; then cleaned_count=$((cleaned_count + 1)); fi
        else
            local reply
            read -r -p "  Remove worktree? (y/N) " reply
            if [[ $reply =~ ^[Yy]$ ]]; then
                remove_worktree "$wt_path" "$wt_branch" "${issue_number:-none}"
                cleaned_count=$((cleaned_count + 1))
            else
                log_skip "Kept: ${wt_path}"
                log_action "SKIPPED" "$wt_path" "$wt_branch" "${issue_number:-none}"
                skipped_count=$((skipped_count + 1))
            fi
        fi

        echo ""
    done < <(list_worktrees)

    echo "--------------------------------------"
    if [[ $stale_count -eq 0 ]]; then
        log_info "No stale worktrees found."
    else
        local mode_label=""
        $DRY_RUN && mode_label=" [DRY-RUN]"
        log_info "Summary${mode_label}: ${stale_count} stale found, ${cleaned_count} cleaned, ${skipped_count} skipped."
        if [[ $cleaned_count -gt 0 ]] || $DRY_RUN; then
            log_info "Log: ${LOG_FILE}"
        fi
    fi
}

main "$@"
