#!/bin/bash
# Helper script to export ANTHROPIC_API_KEY from Claude CLI credentials
# This is necessary for container execution which needs the key in environment

set -euo pipefail

CREDENTIALS_FILE="$HOME/.claude/.credentials.json"

if [[ ! -f "$CREDENTIALS_FILE" ]]; then
    echo "Error: Claude credentials file not found at $CREDENTIALS_FILE" >&2
    echo "Please run 'claude' to authenticate first." >&2
    exit 1
fi

# Extract access token from Claude credentials
API_KEY=$(python3 -c "
import json
import sys
try:
    with open('$CREDENTIALS_FILE', 'r') as f:
        creds = json.load(f)
    token = creds.get('claudeAiOauth', {}).get('accessToken', '')
    if not token:
        print('Error: No access token found in credentials', file=sys.stderr)
        sys.exit(1)
    print(token)
except Exception as e:
    print(f'Error reading credentials: {e}', file=sys.stderr)
    sys.exit(1)
")

if [[ -z "$API_KEY" ]]; then
    echo "Error: Failed to extract API key from credentials" >&2
    exit 1
fi

export ANTHROPIC_API_KEY="$API_KEY"
echo "ANTHROPIC_API_KEY exported successfully"

# If arguments provided, execute them
if [[ $# -gt 0 ]]; then
    exec "$@"
fi
