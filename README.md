# AI Dev Container

Dockerized Claude Code environment with persistent authentication and host-mounted projects.

## Quick Start

```bash
# 1. Build the image (interactive prompts for config)
./build.sh

# 2. Run the container
./run.sh

# 3. On first run, log in inside the container
claude login
# Copy the URL into your host browser to complete OAuth

# 4. Use Claude Code
claude
```

Subsequent `./run.sh` invocations will reuse the saved credentials — no re-login needed.

## Scripts

| Script | Purpose |
|----------|---------|
| `build.sh` | Build the Docker image and configure runtime settings |
| `run.sh [project-dir]` | Start the container with configured mounts |
| `clean.sh` | Remove saved Claude credentials for a fresh start |

## Configuration

`build.sh` prompts for the following and saves them to `.runtime/` (gitignored):

- **SSH key** — Mounted read-only into the container for git operations
- **Git identity** — Name and email passed via environment variables
- **Project directory** — Host directory bind-mounted to `/home/dev/project` (read-write)
- **Persistence mode** — How Claude auth/config is stored between runs:
  - **Mode 1 (default):** Host bind mount at `~/.claude-docker` — files are visible and inspectable on the host
  - **Mode 2:** Docker named volume (`ai-dev-claude`) — managed by Docker, less visible
- **Network mode** — Container networking:
  - **Mode 1 (default):** Bridge — standard Docker networking
  - **Mode 2:** Host — shares host network stack (may help with OAuth callbacks on some setups)

## Project Mount

The project directory is bind-mounted read-write, so changes made inside the container are immediately visible on the host and vice versa. No need to use git to sync.

You can override the project directory at runtime:

```bash
./run.sh /path/to/other/project
```

## Auth Persistence

Claude Code requires two files for authentication:

- `~/.claude/.credentials.json` — OAuth tokens (access + refresh)
- `~/.claude.json` — Account metadata (onboarding state, account info)

Both are stored inside the persistent mount (`~/.claude-docker/` or the named volume). The entrypoint symlinks `~/.claude.json` into the volume so writes are captured across container restarts.

To wipe credentials and force a fresh login:

```bash
./clean.sh
```

## Container Commands

| Command | Description |
|---------|-------------|
| `claude` | Start Claude Code |
| `claude-dsp` | Start Claude Code with `--dangerously-skip-permissions` |

## Architecture

- **Base image:** `debian:bookworm-slim`
- **Claude install:** Native installer (`~/.local/bin/claude`)
- **User:** `dev` (UID/GID matched to host to avoid permission issues)
- **No secrets in the image** — credentials are only in the runtime mount, never baked in
