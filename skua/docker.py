"""Docker operations — build images, run containers, query state."""

import os
import shutil
import subprocess
from pathlib import Path

from skua.config.resources import Environment, SecurityProfile, AgentConfig, Project


def is_container_running(name: str) -> bool:
    """Check if a Docker container with the given name is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"name=^{name}$"],
            capture_output=True, text=True
        )
        return bool(result.stdout.strip())
    except FileNotFoundError:
        return False


def get_running_skua_containers() -> list:
    """Return list of running skua container names."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=^skua-", "--format", "{{.Names}}"],
            capture_output=True, text=True
        )
        if result.stdout.strip():
            return result.stdout.strip().split("\n")
    except FileNotFoundError:
        pass
    return []


# ── Dockerfile generation ────────────────────────────────────────────────

# Core packages always included (required for container operation)
CORE_PACKAGES = [
    "ca-certificates", "curl", "wget", "git", "openssh-client", "sudo", "vim",
]

# Default packages included unless explicitly removed
DEFAULT_PACKAGES = [
    "python3", "python3-pip",
    "procps", "coreutils", "findutils", "grep", "gawk", "sed",
    "less", "tree", "file", "htop", "jq",
    "zip", "unzip", "tar", "gzip", "bzip2", "xz-utils",
    "diffutils", "patch", "man-db", "manpages",
    "net-tools", "iputils-ping", "dnsutils",
]

# Agent install commands keyed by agent name (fallback when no AgentConfig found)
DEFAULT_AGENT_INSTALLS = {
    "claude": ["curl -fsSL https://claude.ai/install.sh | bash"],
}


def generate_dockerfile(
    agent: AgentConfig = None,
    security: SecurityProfile = None,
    base_image: str = "debian:bookworm-slim",
    extra_packages: list = None,
    extra_commands: list = None,
) -> str:
    """Generate a Dockerfile from configuration.

    Args:
        agent: AgentConfig with install commands. Uses claude defaults if None.
        security: SecurityProfile. If agent.sudo is False, sudo is removed.
        base_image: Base Docker image.
        extra_packages: Additional apt packages to install.
        extra_commands: Additional RUN commands to execute.
    """
    packages = list(CORE_PACKAGES)

    # If security says no sudo, we still need sudo during build but remove it after
    remove_sudo = security and not security.agent.sudo

    packages.extend(DEFAULT_PACKAGES)
    if extra_packages:
        packages.extend(extra_packages)

    # Deduplicate while preserving order
    seen = set()
    unique_packages = []
    for p in packages:
        if p not in seen:
            seen.add(p)
            unique_packages.append(p)

    pkg_line = " \\\n    ".join(unique_packages)

    # Agent install commands
    if agent and agent.install.commands:
        install_cmds = agent.install.commands
    else:
        install_cmds = DEFAULT_AGENT_INSTALLS.get("claude", [])

    install_lines = "\n".join(f"RUN {cmd}" for cmd in install_cmds)

    # Extra commands
    extra_lines = ""
    if extra_commands:
        extra_lines = "\n" + "\n".join(f"RUN {cmd}" for cmd in extra_commands)

    # Sudo removal
    sudo_removal = ""
    if remove_sudo:
        sudo_removal = """
# ── Remove sudo (security: agent.sudo=false) ─────────────────────────
RUN sudo deluser dev sudo 2>/dev/null || true && \\
    sudo sed -i '/^dev /d' /etc/sudoers && \\
    sudo rm -f /etc/sudoers.d/* && \\
    sudo chmod 0440 /etc/sudoers
"""

    dockerfile = f"""FROM {base_image}

ARG DEBIAN_FRONTEND=noninteractive
ARG USER_UID=1000
ARG USER_GID=1000

# ── Core system packages ─────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \\
    {pkg_line} \\
    && rm -rf /var/lib/apt/lists/*

# ── Create non-root user (match host UID/GID when possible) ──────────
RUN set -eux; \\
    if ! getent group "$USER_GID" >/dev/null; then groupadd --gid "$USER_GID" dev; fi; \\
    if getent passwd "$USER_UID" >/dev/null; then \\
        existing_user="$(getent passwd "$USER_UID" | cut -d: -f1)"; \\
        if [ "$existing_user" != "dev" ]; then usermod -l dev "$existing_user"; fi; \\
        usermod -d /home/dev -m dev; \\
        usermod -g "$USER_GID" dev; \\
    else \\
        useradd --uid "$USER_UID" --gid "$USER_GID" -m -s /bin/bash dev; \\
    fi; \\
    echo "dev ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# ── Install agent ────────────────────────────────────────────────────
USER dev
{install_lines}
WORKDIR /home/dev
{extra_lines}

# ── Non-sensitive config defaults (copied into volume on first run) ──
COPY --chown=dev:dev claude-settings/ /home/dev/.claude-defaults/

# ── Placeholder directories ─────────────────────────────────────────
RUN mkdir -p /home/dev/.ssh /home/dev/project /home/dev/.claude

# ── Environment ──────────────────────────────────────────────────────
ENV EDITOR=vim
ENV PATH="/home/dev/.local/bin:${{PATH}}"
{sudo_removal}
# ── Entrypoint ───────────────────────────────────────────────────────
COPY --chown=dev:dev entrypoint.sh /home/dev/entrypoint.sh
RUN chmod +x /home/dev/entrypoint.sh

ENTRYPOINT ["/home/dev/entrypoint.sh"]
"""
    return dockerfile


# ── Build ────────────────────────────────────────────────────────────────

def build_image(
    container_dir: Path,
    image_name: str,
    security: SecurityProfile = None,
    agent: AgentConfig = None,
    base_image: str = "debian:bookworm-slim",
    extra_packages: list = None,
    extra_commands: list = None,
):
    """Build a Docker image, generating the Dockerfile from config.

    Uses container_dir for entrypoint.sh and Claude settings.
    """
    build_path = container_dir / ".build-context"
    try:
        if build_path.exists():
            shutil.rmtree(build_path)
        build_path.mkdir()

        # Generate Dockerfile
        dockerfile_content = generate_dockerfile(
            agent=agent,
            security=security,
            base_image=base_image,
            extra_packages=extra_packages,
            extra_commands=extra_commands,
        )
        (build_path / "Dockerfile").write_text(dockerfile_content)

        # Copy entrypoint
        shutil.copy2(container_dir / "entrypoint.sh", build_path / "entrypoint.sh")

        # Copy Claude settings (no credentials)
        settings_dir = build_path / "claude-settings"
        settings_dir.mkdir()
        claude_home = Path.home() / ".claude"
        for fname in ("settings.json", "settings.local.json"):
            src = claude_home / fname
            if src.exists():
                shutil.copy2(src, settings_dir / fname)

        uid = os.getuid()
        gid = os.getgid()
        cmd = [
            "docker", "build",
            "--build-arg", f"USER_UID={uid}",
            "--build-arg", f"USER_GID={gid}",
            "-t", image_name,
            str(build_path),
        ]
        result = subprocess.run(cmd)
        return result.returncode == 0

    finally:
        if build_path.exists():
            shutil.rmtree(build_path, ignore_errors=True)


# ── Run command construction ─────────────────────────────────────────────

def build_run_command(
    project: Project,
    environment: Environment,
    security: SecurityProfile,
    agent: AgentConfig,
    image_name: str,
    data_dir: Path,
) -> list:
    """Build the docker run command list from resolved configuration."""
    container_name = f"skua-{project.name}"

    docker_cmd = [
        "docker", "run", "-it", "--rm",
        "--name", container_name,
    ]

    # Container runtime (gVisor, Kata, etc.)
    container_runtime = environment.docker.container_runtime
    if container_runtime:
        docker_cmd.extend(["--runtime", container_runtime])

    # Git identity
    if project.git.name:
        docker_cmd.extend(["-e", f"GIT_AUTHOR_NAME={project.git.name}"])
        docker_cmd.extend(["-e", f"GIT_AUTHOR_EMAIL={project.git.email}"])
        docker_cmd.extend(["-e", f"GIT_COMMITTER_NAME={project.git.name}"])
        docker_cmd.extend(["-e", f"GIT_COMMITTER_EMAIL={project.git.email}"])

    # SSH key mounts
    ssh_key = project.ssh.private_key
    if ssh_key and Path(ssh_key).is_file():
        key_name = Path(ssh_key).name
        docker_cmd.extend(["-v", f"{ssh_key}:/home/dev/.ssh-mount/{key_name}:ro"])
        pub_key = f"{ssh_key}.pub"
        if Path(pub_key).is_file():
            docker_cmd.extend(["-v", f"{pub_key}:/home/dev/.ssh-mount/{key_name}.pub:ro"])
        known_hosts = Path(ssh_key).parent / "known_hosts"
        if known_hosts.is_file():
            docker_cmd.extend(["-v", f"{known_hosts}:/home/dev/.ssh-mount/known_hosts:ro"])

    # Project directory mount
    if project.directory and Path(project.directory).is_dir():
        docker_cmd.extend(["-v", f"{project.directory}:/home/dev/project"])

    # Persistence mount
    if environment.persistence.mode == "bind":
        data_dir.mkdir(parents=True, exist_ok=True)
        docker_cmd.extend(["-v", f"{data_dir}:/home/dev/.claude"])
    else:
        vol_name = f"skua-{project.name}-claude"
        docker_cmd.extend(["-v", f"{vol_name}:/home/dev/.claude"])

    # Network mode
    net = environment.network.mode
    if net == "host":
        docker_cmd.append("--network=host")
    elif net == "none":
        docker_cmd.append("--network=none")
    elif net == "internal":
        # For plain docker driver, internal means no network
        # (true internal networks require compose)
        if environment.driver == "docker":
            docker_cmd.append("--network=none")

    docker_cmd.append(image_name)
    return docker_cmd


# ── Container operations ─────────────────────────────────────────────────

def exec_into_container(container_name: str):
    """Exec into a running container, replacing this process."""
    os.execvp("docker", ["docker", "exec", "-it", container_name, "/bin/bash"])


def run_container(docker_cmd: list):
    """Replace this process with docker run (execvp)."""
    os.execvp("docker", docker_cmd)
