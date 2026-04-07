#!/usr/bin/env bats
# Tests for the project justfile — verifies recipes exist and stay in sync

REPO_ROOT="$(git -C "$(dirname "$BATS_TEST_FILENAME")" rev-parse --show-toplevel)"
JUSTFILE="${REPO_ROOT}/justfile"

# ---------------------------------------------------------------------------
# Existence
# ---------------------------------------------------------------------------

@test "justfile exists at project root" {
    [ -f "$JUSTFILE" ]
}

# ---------------------------------------------------------------------------
# just --list succeeds
# ---------------------------------------------------------------------------

@test "just --list succeeds" {
    run just --justfile "$JUSTFILE" --list
    [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Expected recipes are present
# ---------------------------------------------------------------------------

@test "justfile contains 'test' recipe" {
    run just --justfile "$JUSTFILE" --list
    [[ "$output" == *"test "* ]] || [[ "$output" == *"test"$'\n'* ]]
}

@test "justfile contains 'lint' recipe" {
    run just --justfile "$JUSTFILE" --list
    [[ "$output" == *"lint "* ]] || [[ "$output" == *"lint"$'\n'* ]]
}

@test "justfile contains 'format' recipe" {
    run just --justfile "$JUSTFILE" --list
    [[ "$output" == *"format "* ]] || [[ "$output" == *"format"$'\n'* ]]
}

@test "justfile contains 'typecheck' recipe" {
    run just --justfile "$JUSTFILE" --list
    [[ "$output" == *"typecheck"* ]]
}

@test "justfile contains 'pre-commit' recipe" {
    run just --justfile "$JUSTFILE" --list
    [[ "$output" == *"pre-commit"* ]]
}

@test "justfile contains 'audit' recipe" {
    run just --justfile "$JUSTFILE" --list
    [[ "$output" == *"audit"* ]]
}

@test "justfile contains 'ci-all' recipe" {
    run just --justfile "$JUSTFILE" --list
    [[ "$output" == *"ci-all"* ]]
}

# ---------------------------------------------------------------------------
# No heredocs (regression guard — known pitfall with just)
# ---------------------------------------------------------------------------

@test "justfile contains no heredocs" {
    run grep -cE '<<\s*[A-Z_"'"'"']' "$JUSTFILE"
    # grep -c returns 1 (failure) when count is 0 — that is the success case
    [ "$status" -eq 1 ] || [ "$output" = "0" ]
}

# ---------------------------------------------------------------------------
# Every pixi [tasks] key has a matching justfile recipe
# ---------------------------------------------------------------------------

@test "all pixi tasks have a corresponding just recipe" {
    # Extract task names from [tasks] section of pixi.toml
    local pixi_toml="${REPO_ROOT}/pixi.toml"
    [ -f "$pixi_toml" ] || skip "pixi.toml not found"

    # Get just recipe names
    local just_recipes
    just_recipes="$(just --justfile "$JUSTFILE" --list 2>/dev/null | tail -n +2 | awk '{print $1}')"

    # Parse [tasks] keys (lines matching key = "..." under [tasks], skip comments)
    local missing=""
    while IFS= read -r task; do
        # typecheck is not a pixi task but a just-only recipe — skip plan-issues
        # since it's a script utility, not a developer workflow
        case "$task" in
            plan-issues) continue ;;
        esac
        if ! echo "$just_recipes" | grep -qx "$task"; then
            missing="${missing} ${task}"
        fi
    done < <(sed -n '/^\[tasks\]/,/^\[/{ /^\[/d; /^#/d; /^$/d; s/ *=.*//p; }' "$pixi_toml")

    if [ -n "$missing" ]; then
        echo "pixi tasks missing from justfile:${missing}" >&2
        return 1
    fi
}
