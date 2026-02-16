#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/.build-context"
RUNTIME_DIR="$SCRIPT_DIR/.runtime"
IMAGE_NAME="ai-dev"

echo "============================================"
echo "  AI Dev Container Builder"
echo "  Claude Code"
echo "============================================"
echo ""
echo "No secrets are baked into the image."
echo "Claude Code handles auth via browser login"
echo "URLs (open them in your host browser)."
echo ""

# ── Prompt for SSH key pair ───────────────────────────────────────────
echo "Available SSH keys:"
for pub in "$HOME/.ssh"/*.pub; do
    [ -f "$pub" ] && echo "  ${pub%.pub}"
done
echo ""
read -rp "Path to SSH private key (leave empty to skip): " SSH_KEY
if [ -n "$SSH_KEY" ] && [ -f "$SSH_KEY" ]; then
    SSH_PUB="${SSH_KEY}.pub"
    if [ ! -f "$SSH_PUB" ]; then
        echo "Warning: no matching public key at $SSH_PUB"
    fi
fi

# ── Prompt for git identity ──────────────────────────────────────────
echo ""
DEFAULT_GIT_NAME=$(git config --global user.name 2>/dev/null || echo "")
DEFAULT_GIT_EMAIL=$(git config --global user.email 2>/dev/null || echo "")
read -rp "Git user name [$DEFAULT_GIT_NAME]: " GIT_NAME
GIT_NAME="${GIT_NAME:-$DEFAULT_GIT_NAME}"
read -rp "Git user email [$DEFAULT_GIT_EMAIL]: " GIT_EMAIL
GIT_EMAIL="${GIT_EMAIL:-$DEFAULT_GIT_EMAIL}"

# ── Prompt for project directory ─────────────────────────────────────
echo ""
read -rp "Project directory to mount (leave empty to skip): " PROJECT_DIR

# ── Prompt for Claude config persistence ────────────────────────────
echo ""
echo "Claude auth/config persistence options:"
echo "  1) Host bind mount (recommended - visible at ~/.claude-docker)"
echo "  2) Docker named volume (ai-dev-claude)"
read -rp "Persistence mode [1]: " PERSIST_MODE
PERSIST_MODE="${PERSIST_MODE:-1}"

# ── Save runtime config (gitignored, never enters image) ────────────
echo ""
echo "Saving runtime config..."
mkdir -p "$RUNTIME_DIR"

cat > "$RUNTIME_DIR/.env" <<EOF
GIT_AUTHOR_NAME=$GIT_NAME
GIT_AUTHOR_EMAIL=$GIT_EMAIL
GIT_COMMITTER_NAME=$GIT_NAME
GIT_COMMITTER_EMAIL=$GIT_EMAIL
EOF

cat > "$RUNTIME_DIR/paths.conf" <<EOF
SSH_KEY=$SSH_KEY
PROJECT_DIR=$PROJECT_DIR
PERSIST_MODE=$PERSIST_MODE
EOF

# ── Build context (no secrets) ───────────────────────────────────────
echo "Preparing build context..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Static files
cp "$SCRIPT_DIR/Dockerfile" "$BUILD_DIR/"
cp "$SCRIPT_DIR/entrypoint.sh" "$BUILD_DIR/"

# Claude settings only (NO credentials)
echo "Copying Claude settings (no credentials)..."
mkdir -p "$BUILD_DIR/claude-settings"
for f in settings.json settings.local.json; do
    if [ -f "$HOME/.claude/$f" ]; then
        cp "$HOME/.claude/$f" "$BUILD_DIR/claude-settings/"
    fi
done

# ── Build ────────────────────────────────────────────────────────────
echo ""
echo "Building Docker image '$IMAGE_NAME'..."
docker build \
    --build-arg USER_UID="$(id -u)" \
    --build-arg USER_GID="$(id -g)" \
    -t "$IMAGE_NAME" \
    "$BUILD_DIR"

# ── Cleanup build context ───────────────────────────────────────────
rm -rf "$BUILD_DIR"

echo ""
echo "============================================"
echo "  Build complete: $IMAGE_NAME"
echo "============================================"
echo ""
echo "Image contains NO secrets."
echo "On first run, log in to each service:"
echo "  claude login     (copy the URL into your host browser)"
echo ""
echo "Run with:  ./run.sh"
echo ""
