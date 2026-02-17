<p align="center">
  <img src="docs/logo.png" alt="Skua logo" width="300">
</p>

# Skua — Dockerized Claude Code Manager

Run Claude Code in isolated Docker containers with configurable security profiles, multi-project support, and persistent authentication.

## Quick Start

```bash
git clone https://github.com/WilliamScarbro/skua.git
cd skua
./install.sh
```

Then add a project and start working:

```bash
skua add myapp --dir ~/projects/myapp
skua run myapp

# Inside the container:
claude login    # copy the URL into your host browser
```

Subsequent runs reuse saved credentials — no re-login needed.

### Prerequisites

- Docker (daemon running)
- Python 3 + PyYAML
- git

### Alternative: .deb Package

```bash
sudo dpkg -i skua_<version>_all.deb
skua init
skua build
```

### Manual Setup

```bash
pip install pyyaml
ln -s /path/to/skua/bin/skua ~/.local/bin/skua
skua init
skua build
```

## Commands

| Command | Purpose |
|---------|---------|
| `skua init` | First-time setup wizard |
| `skua build` | Build the base Docker image |
| `skua add <name>` | Add a project |
| `skua remove <name>` | Remove a project |
| `skua run <name>` | Start a container (or attach if running) |
| `skua list` | List projects and running status |
| `skua clean [name]` | Remove saved credentials |
| `skua config` | Show or edit global configuration |
| `skua validate <name>` | Validate project configuration |
| `skua describe <name>` | Show resolved configuration as YAML |

## Security Profiles

Skua uses Kubernetes-style YAML resources to configure security. Four shipped profiles:

| Profile | Sudo | Network | Installs | Mode Required |
|---------|------|---------|----------|---------------|
| **open** | yes | direct | unrestricted | unmanaged |
| **standard** | yes | direct | advisory (logged) | unmanaged |
| **hardened** | no | proxy-mediated | verified | managed |
| **airgapped** | no | none | none | any |

```bash
skua add myapp --dir ~/projects/myapp --security standard
skua validate myapp
```

## Environments

Environments describe where containers run and what security features they support:

| Environment | Mode | Isolation | Use For |
|-------------|------|-----------|---------|
| `local-docker` | unmanaged | container | Simple development |
| `local-docker-gvisor` | unmanaged | gVisor kernel sandbox | Stronger isolation |
| `local-compose` | managed | container + sidecar | Hardened/proxy security |

**Unmanaged**: single container, skua launches and exits. Simple, lightweight.

**Managed**: skua sidecar alongside the agent. Trusted proxy, verified monitoring, MCP endpoints.

```bash
skua add myapp --dir ~/projects/myapp --env local-docker-gvisor
```

## Configuration

All config lives in `~/.config/skua/` as YAML resources:

```
~/.config/skua/
├── global.yaml          # git identity, defaults
├── environments/        # where containers run
├── security/            # what agents can do
├── agents/              # how agents are installed
└── projects/            # ties it all together
```

Skua validates that security requirements match environment capabilities before running.

```bash
skua config                              # view config
skua config --git-name "Your Name"       # set git identity
skua config --default-security standard  # change default profile
```

## Architecture

- **Declarative YAML**: Kubernetes-style resources with cross-resource validation
- **Launcher model**: `skua run` replaces itself via `execvp` — launch and walk away
- **Trust boundary**: Agent has admin inside the container; enforceable controls are external (Docker network, sudo removal, sidecar proxy)
- **Dynamic Dockerfiles**: Generated from config (base image, packages, agent, security)
- **No secrets in images**: Credentials live only in runtime mounts
- **Project isolation**: Each project has its own container, credentials, and mount

## Documentation

- **[Quick Start](docs/quickstart.md)** — installation and first project
- **[CLI Reference](docs/cli.md)** — all commands and options
- **[Security Guide](docs/security.md)** — profiles, trust model, isolation
- **[Configuration Model](docs/configuration.md)** — YAML resources, capabilities, validation

## License

Business Source License 1.1 — see [LICENSE](LICENSE).
