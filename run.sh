#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_DIR="$SCRIPT_DIR/.runtime"
IMAGE_NAME="ai-dev"
CONTAINER_NAME="ai-dev-session"

# ── Load runtime config ─────────────────────────────────────────────
if [ ! -f "$RUNTIME_DIR/.env" ] || [ ! -f "$RUNTIME_DIR/paths.conf" ]; then
    echo "Runtime config not found. Run ./build.sh first."
    exit 1
fi

source "$RUNTIME_DIR/paths.conf"

# ── Volume mounts ────────────────────────────────────────────────────
MOUNT_ARGS=""

# SSH key pair (read-only, individual files)
if [ -n "$SSH_KEY" ] && [ -f "$SSH_KEY" ]; then
    KEY_NAME="$(basename "$SSH_KEY")"
    MOUNT_ARGS="$MOUNT_ARGS -v $SSH_KEY:/home/dev/.ssh-mount/$KEY_NAME:ro"
    if [ -f "${SSH_KEY}.pub" ]; then
        MOUNT_ARGS="$MOUNT_ARGS -v ${SSH_KEY}.pub:/home/dev/.ssh-mount/${KEY_NAME}.pub:ro"
    fi
    SSH_DIR="$(dirname "$SSH_KEY")"
    if [ -f "$SSH_DIR/known_hosts" ]; then
        MOUNT_ARGS="$MOUNT_ARGS -v $SSH_DIR/known_hosts:/home/dev/.ssh-mount/known_hosts:ro"
    fi
fi

# Project directory (read-write)
if [ -n "$PROJECT_DIR" ] && [ -d "$PROJECT_DIR" ]; then
    MOUNT_ARGS="$MOUNT_ARGS -v $PROJECT_DIR:/home/dev/project"
fi

# Persistent Claude auth + config (survive container restarts)
CLAUDE_HOST_DIR="$HOME/.claude-docker"
if [ "${PERSIST_MODE:-1}" = "1" ]; then
    mkdir -p "$CLAUDE_HOST_DIR"
    MOUNT_ARGS="$MOUNT_ARGS -v $CLAUDE_HOST_DIR:/home/dev/.claude"
    # Seed .claude.json from host only if credentials already exist
    # (i.e. user has logged in before — don't re-seed after clean.sh)
    if [ ! -f "$CLAUDE_HOST_DIR/.claude.json" ] && [ -f "$CLAUDE_HOST_DIR/.credentials.json" ] && [ -f "$HOME/.claude.json" ]; then
        cp "$HOME/.claude.json" "$CLAUDE_HOST_DIR/.claude.json"
        echo "Seeded .claude.json from host into $CLAUDE_HOST_DIR"
    fi
else
    MOUNT_ARGS="$MOUNT_ARGS -v ai-dev-claude:/home/dev/.claude"
fi

# Override project dir via CLI arg
if [ -n "$1" ]; then
    OVERRIDE_DIR="$(cd "$1" && pwd)"
    echo "Overriding project mount: $OVERRIDE_DIR"
    MOUNT_ARGS=$(echo "$MOUNT_ARGS" | sed 's|-v [^ ]*/home/dev/project||g')
    MOUNT_ARGS="$MOUNT_ARGS -v $OVERRIDE_DIR:/home/dev/project"
fi

echo "Starting AI Dev Container..."
echo "  Network:  host (login callbacks use host localhost)"
echo "  SSH key:  ${SSH_KEY:-none}"
echo "  Project:  ${PROJECT_DIR:-none}"
if [ "${PERSIST_MODE:-1}" = "1" ]; then
    echo "  Claude:   bind mount -> $CLAUDE_HOST_DIR"
else
    echo "  Claude:   named volume -> ai-dev-claude"
fi
echo ""
echo "To log in, copy the URLs printed by Claude Code"
echo "and open them in your host browser."
echo ""

docker run -it --rm \
    --name "$CONTAINER_NAME" \
    --network=host \
    --env-file "$RUNTIME_DIR/.env" \
    $MOUNT_ARGS \
    "$IMAGE_NAME"
