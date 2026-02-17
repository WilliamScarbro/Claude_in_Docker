"""skua build — build the Docker image."""

import sys

from skua.config import ConfigStore
from skua.docker import build_image


def cmd_build(args):
    store = ConfigStore()

    if not store.is_initialized():
        print("Skua is not initialized. Run 'skua init' first.")
        sys.exit(1)

    container_dir = store.get_container_dir()
    if container_dir is None:
        print("Error: Cannot find container build assets (entrypoint.sh).")
        print("Set toolDir in global.yaml or reinstall skua.")
        sys.exit(1)

    # Determine image name
    g = store.load_global()
    image_name = g.get("imageName", "skua-base")
    base_image = g.get("baseImage", "debian:bookworm-slim")

    # Load security and agent configs
    defaults = g.get("defaults", {})
    security_name = defaults.get("security", "open")
    agent_name = defaults.get("agent", "claude")
    security = store.load_security(security_name)
    agent = store.load_agent(agent_name)

    # Collect extra packages/commands from global config
    image_config = g.get("image", {})
    extra_packages = image_config.get("extraPackages", [])
    extra_commands = image_config.get("extraCommands", [])

    print(f"Building Docker image '{image_name}'...")
    print(f"  Base image:  {base_image}")
    print(f"  Security:    {security_name}")
    print(f"  Agent:       {agent_name}")
    if extra_packages:
        print(f"  Extra pkgs:  {', '.join(extra_packages)}")
    print(f"  Source:      {container_dir}")
    print()

    success = build_image(
        container_dir=container_dir,
        image_name=image_name,
        security=security,
        agent=agent,
        base_image=base_image,
        extra_packages=extra_packages,
        extra_commands=extra_commands,
    )

    print(f"\nBuild complete: {image_name}")
    print("Run 'skua add <name> --dir <path>' to add a project.")
