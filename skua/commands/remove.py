"""skua remove — remove a project configuration."""

import shutil
import subprocess
import sys

from skua.config import ConfigStore
from skua.docker import is_container_running
from skua.utils import confirm


def cmd_remove(args):
    store = ConfigStore()
    name = args.name

    project = store.load_project(name)
    if project is None:
        print(f"Error: Project '{name}' not found.")
        sys.exit(1)

    container_name = f"skua-{name}"
    if is_container_running(container_name):
        print(f"Error: Container '{container_name}' is running. Stop it first.")
        sys.exit(1)

    env = store.load_environment(project.environment)

    # Remove project resource file
    store.delete_resource("Project", name)
    print(f"Project '{name}' removed from config.")

    # Offer to clean data
    persist_mode = env.persistence.mode if env else "bind"
    if persist_mode == "bind":
        data_dir = store.claude_data_dir(name)
        if data_dir.exists():
            if confirm(f"Also remove Claude data at {data_dir}?"):
                shutil.rmtree(data_dir)
                print("  Claude data removed.")
    else:
        vol_name = f"skua-{name}-claude"
        if confirm(f"Also remove Docker volume '{vol_name}'?"):
            subprocess.run(["docker", "volume", "rm", vol_name], capture_output=True)
            print("  Docker volume removed.")
