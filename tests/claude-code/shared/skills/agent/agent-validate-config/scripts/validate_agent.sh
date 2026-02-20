#!/usr/bin/env bash
#
# Validate a single agent configuration file
#
# Usage:
#   ./validate_agent.sh <agent-file>

set -euo pipefail

AGENT_FILE="${1:-}"

if [[ -z "$AGENT_FILE" ]] || [[ ! -f "$AGENT_FILE" ]]; then
    echo "Error: Valid agent file required"
    echo "Usage: $0 <agent-file>"
    exit 1
fi

echo "Validating: $AGENT_FILE"
echo ""

ERRORS=0

# Extract YAML frontmatter
FRONTMATTER=$(sed -n '/^---$/,/^---$/p' "$AGENT_FILE" | sed '1d;$d')

if [[ -z "$FRONTMATTER" ]]; then
    echo "❌ No YAML frontmatter found"
    ((ERRORS++))
    exit 1
fi

echo "✅ YAML frontmatter found"

# Check required fields
REQUIRED_FIELDS=("name" "role" "level" "phase" "description")

for field in "${REQUIRED_FIELDS[@]}"; do
    if echo "$FRONTMATTER" | grep -q "^$field:"; then
        echo "✅ Required field: $field"
    else
        echo "❌ Missing required field: $field"
        ((ERRORS++))
    fi
done

# Validate level (must be 0-5)
LEVEL=$(echo "$FRONTMATTER" | grep "^level:" | cut -d':' -f2 | tr -d ' ')
if [[ -n "$LEVEL" ]]; then
    if [[ "$LEVEL" =~ ^[0-5]$ ]]; then
        echo "✅ Valid level: $LEVEL"
    else
        echo "❌ Invalid level: $LEVEL (must be 0-5)"
        ((ERRORS++))
    fi
fi

# Validate phase
PHASE=$(echo "$FRONTMATTER" | grep "^phase:" | cut -d':' -f2 | tr -d ' ')
if [[ -n "$PHASE" ]]; then
    VALID_PHASES=("Plan" "Test" "Implementation" "Package" "Cleanup")
    PHASE_VALID=false
    for valid_phase in "${VALID_PHASES[@]}"; do
        if [[ "$PHASE" == "$valid_phase" ]]; then
            PHASE_VALID=true
            break
        fi
    done
    if [[ "$PHASE_VALID" == "true" ]]; then
        echo "✅ Valid phase: $PHASE"
    else
        echo "❌ Invalid phase: $PHASE"
        echo "   Valid phases: ${VALID_PHASES[*]}"
        ((ERRORS++))
    fi
fi

# Validate tools (if present)
if echo "$FRONTMATTER" | grep -q "^tools:"; then
    VALID_TOOLS=("Read" "Write" "Edit" "Bash" "Grep" "Glob" "Task" "WebFetch" "WebSearch" "TodoWrite" "SlashCommand" "AskUserQuestion" "NotebookEdit" "BashOutput" "KillShell")
    TOOLS_LINE=$(echo "$FRONTMATTER" | grep "^tools:" | cut -d':' -f2-)

    # Check format: must be [tool1,tool2,...] bracketed list
    if [[ "$TOOLS_LINE" =~ \[.*\] ]]; then
        echo "✅ Tools field properly formatted"
        # Strip brackets and split on commas
        TOOLS_CONTENT="${TOOLS_LINE//[/}"
        TOOLS_CONTENT="${TOOLS_CONTENT//]/}"
        IFS=',' read -ra TOOL_LIST <<< "$TOOLS_CONTENT"
        for tool_entry in "${TOOL_LIST[@]}"; do
            tool_name=$(echo "$tool_entry" | tr -d ' ')
            [[ -z "$tool_name" ]] && continue
            TOOL_VALID=false
            for valid_tool in "${VALID_TOOLS[@]}"; do
                if [[ "$tool_name" == "$valid_tool" ]]; then
                    TOOL_VALID=true
                    break
                fi
            done
            if [[ "$TOOL_VALID" == "true" ]]; then
                echo "✅ Valid tool: $tool_name"
            else
                echo "❌ Invalid tool: $tool_name"
                echo "   Valid tools: ${VALID_TOOLS[*]}"
                ((ERRORS++))
            fi
        done
    else
        echo "⚠️  Tools field may be improperly formatted"
    fi
fi

echo ""
if [[ $ERRORS -eq 0 ]]; then
    echo "✅ Validation passed"
    exit 0
else
    echo "❌ Validation failed with $ERRORS error(s)"
    exit 1
fi
