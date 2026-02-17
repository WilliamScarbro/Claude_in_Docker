"""skua run — start or attach to a container for a project."""

import shutil
import subprocess
import sys
from pathlib import Path

from skua.config import ConfigStore, validate_project
from skua.docker import (
    is_container_running,
    exec_into_container,
    build_run_command,
    run_container,
)


def cmd_run(args):
    store = ConfigStore()
    name = args.name

    project = store.resolve_project(name)
    if project is None:
        print(f"Error: Project '{name}' not found. Add it with: skua add {name}")
        sys.exit(1)

    container_name = f"skua-{name}"

    # Check if already running
    if is_container_running(container_name):
        print(f"Container '{container_name}' is already running.")
        answer = input("Attach to it? [Y/n]: ").strip().lower()
        if answer != "n":
            exec_into_container(container_name)
        return

    # Load referenced resources
    env = store.load_environment(project.environment)
    sec = store.load_security(project.security)
    agent = store.load_agent(project.agent)

    if env is None:
        print(f"Error: Environment '{project.environment}' not found.")
        sys.exit(1)
    if sec is None:
        print(f"Error: Security profile '{project.security}' not found.")
        sys.exit(1)
    if agent is None:
        print(f"Error: Agent '{project.agent}' not found.")
        sys.exit(1)

    # Validate configuration
    result = validate_project(project, env, sec, agent)
    if result.warnings:
        for w in result.warnings:
            print(f"  Warning: {w}")
    if not result.valid:
        print("\nConfiguration validation failed:")
        for e in result.errors:
            print(f"  x {e}")
        print("\nRun 'skua validate' for details, or fix the configuration.")
        sys.exit(1)

    # Clone repo if needed
    if project.repo:
        clone_dir = store.repo_dir(name)
        if not clone_dir.exists():
            print(f"Cloning {project.repo} into {clone_dir}...")
            clone_cmd = ["git", "clone"]
            if project.ssh.private_key:
                ssh_cmd = f"ssh -i {project.ssh.private_key} -o StrictHostKeyChecking=no"
                clone_cmd = ["git", "-c", f"core.sshCommand={ssh_cmd}", "clone"]
            clone_cmd += [project.repo, str(clone_dir)]
            try:
                subprocess.run(clone_cmd, check=True)
            except subprocess.CalledProcessError:
                print(f"Error: Failed to clone {project.repo}")
                sys.exit(1)
        else:
            print(f"Using existing clone at {clone_dir}")
        project.directory = str(clone_dir)

    # Determine image name
    g = store.load_global()
    image_name = g.get("imageName", "skua-base")

    # Build persistence path
    data_dir = store.claude_data_dir(name)

    # Seed .claude.json from host if needed
    if env.persistence.mode == "bind":
        data_dir.mkdir(parents=True, exist_ok=True)
        claude_json_dest = data_dir / ".claude.json"
        creds_file = data_dir / ".credentials.json"
        host_claude_json = Path.home() / ".claude.json"
        if not claude_json_dest.exists() and creds_file.exists() and host_claude_json.exists():
            shutil.copy2(host_claude_json, claude_json_dest)
            print("Seeded .claude.json from host.")

    # Build and exec docker command
    docker_cmd = build_run_command(
        project=project,
        environment=env,
        security=sec,
        agent=agent,
        image_name=image_name,
        data_dir=data_dir,
    )

    # Print summary
    print(f"Starting skua-{name}...")
    print(f"  Project:     {project.directory or '(none)'}")
    print(f"  Environment: {project.environment}")
    print(f"  Security:    {project.security}")
    print(f"  Agent:       {project.agent}")
    ssh_display = Path(project.ssh.private_key).name if project.ssh.private_key else "(none)"
    print(f"  SSH key:     {ssh_display}")
    print(f"  Network:     {env.network.mode}")
    if env.persistence.mode == "bind":
        print(f"  Claude:      {data_dir}")
    else:
        print(f"  Claude:      volume skua-{name}-claude")
    print()

    run_container(docker_cmd)
