FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive
ARG USER_UID=1000
ARG USER_GID=1000

# ── Core system packages ─────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget git openssh-client sudo vim \
    python3 python3-pip \
    procps coreutils findutils grep gawk sed \
    less tree file htop jq zip unzip tar gzip bzip2 xz-utils \
    diffutils patch man-db manpages \
    net-tools iputils-ping dnsutils \
    && rm -rf /var/lib/apt/lists/*

# ── Create non-root user (match host UID/GID when possible) ──────────
RUN set -eux; \
    if ! getent group "$USER_GID" >/dev/null; then groupadd --gid "$USER_GID" dev; fi; \
    if getent passwd "$USER_UID" >/dev/null; then \
        existing_user="$(getent passwd "$USER_UID" | cut -d: -f1)"; \
        if [ "$existing_user" != "dev" ]; then usermod -l dev "$existing_user"; fi; \
        usermod -d /home/dev -m dev; \
        usermod -g "$USER_GID" dev; \
    else \
        useradd --uid "$USER_UID" --gid "$USER_GID" -m -s /bin/bash dev; \
    fi; \
    echo "dev ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# ── Install Claude Code (native installer) ───────────────────────────
USER dev
RUN curl -fsSL https://claude.ai/install.sh | bash
WORKDIR /home/dev

# ── Non-sensitive config defaults (copied into volume on first run) ──
COPY --chown=dev:dev claude-settings/ /home/dev/.claude-defaults/

# ── Placeholder directories ─────────────────────────────────────────
RUN mkdir -p /home/dev/.ssh /home/dev/project /home/dev/.claude

# ── Environment ──────────────────────────────────────────────────────
ENV EDITOR=vim
ENV PATH="/home/dev/.local/bin:${PATH}"

# ── Entrypoint ───────────────────────────────────────────────────────
COPY --chown=dev:dev entrypoint.sh /home/dev/entrypoint.sh
RUN chmod +x /home/dev/entrypoint.sh

ENTRYPOINT ["/home/dev/entrypoint.sh"]
