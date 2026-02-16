#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_DIR="$SCRIPT_DIR/.runtime"
CLAUDE_HOST_DIR="$HOME/.claude-docker"

echo "AI Dev Container - Clean Credentials"
echo ""

# Determine persistence mode
PERSIST_MODE="1"
if [ -f "$RUNTIME_DIR/paths.conf" ]; then
    source "$RUNTIME_DIR/paths.conf"
fi

if [ "${PERSIST_MODE}" = "1" ]; then
    if [ -d "$CLAUDE_HOST_DIR" ]; then
        echo "Cleaning credentials from: $CLAUDE_HOST_DIR"
        rm -f "$CLAUDE_HOST_DIR/.credentials.json"
        rm -f "$CLAUDE_HOST_DIR/.claude.json"
        echo "  Removed .credentials.json and .claude.json"
    else
        echo "Nothing to clean: $CLAUDE_HOST_DIR does not exist."
    fi
else
    echo "Removing Docker named volume: ai-dev-claude"
    docker volume rm ai-dev-claude 2>/dev/null && echo "  Done." || echo "  Volume not found or in use."
fi

echo ""
echo "Next run of ./run.sh will require a fresh 'claude login'."
