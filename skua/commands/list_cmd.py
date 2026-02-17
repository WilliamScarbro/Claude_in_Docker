"""skua list — list projects and running containers."""

from pathlib import Path

from skua.config import ConfigStore
from skua.docker import get_running_skua_containers


def cmd_list(args):
    store = ConfigStore()
    project_names = store.list_resources("Project")
    running = get_running_skua_containers()

    if not project_names:
        print("No projects configured. Add one with: skua add <name> --dir <path> or --repo <url>")
        return

    # Header
    print(f"{'NAME':<16} {'DIRECTORY':<36} {'SECURITY':<12} {'NETWORK':<10} {'STATUS':<10}")
    print("-" * 84)

    for name in project_names:
        project = store.load_project(name)
        if project is None:
            continue
        container_name = f"skua-{name}"
        status = "running" if container_name in running else "stopped"
        proj_dir = project.directory or project.repo or "(none)"

        # Shorten home paths
        try:
            proj_dir = "~/" + str(Path(proj_dir).relative_to(Path.home()))
        except (ValueError, TypeError):
            pass

        env = store.load_environment(project.environment)
        network = env.network.mode if env else "?"

        print(f"{name:<16} {proj_dir:<36} {project.security:<12} {network:<10} {status:<10}")

    print()
    running_count = sum(1 for n in project_names if f"skua-{n}" in running)
    print(f"{len(project_names)} project(s), {running_count} running")
