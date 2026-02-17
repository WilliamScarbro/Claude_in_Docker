"""skua clean — clean Claude credentials."""

import subprocess
import sys

from skua.config import ConfigStore
from skua.utils import confirm


def cmd_clean(args):
    store = ConfigStore()
    name = args.name

    if name:
        project = store.load_project(name)
        if project is None:
            print(f"Error: Project '{name}' not found.")
            sys.exit(1)
        env = store.load_environment(project.environment)
        _clean_project(store, name, env)
    else:
        project_names = store.list_resources("Project")
        if not project_names:
            print("No projects configured.")
            return
        if not confirm("Clean Claude credentials for ALL projects?"):
            return
        for pname in project_names:
            project = store.load_project(pname)
            env = store.load_environment(project.environment) if project else None
            _clean_project(store, pname, env)


def _clean_project(store, name, env):
    persist_mode = env.persistence.mode if env else "bind"
    if persist_mode == "bind":
        data_dir = store.claude_data_dir(name)
        if data_dir.exists():
            for fname in (".credentials.json", ".claude.json"):
                f = data_dir / fname
                if f.exists():
                    f.unlink()
            print(f"Cleaned credentials for '{name}'.")
        else:
            print(f"No data to clean for '{name}'.")
    else:
        vol_name = f"skua-{name}-claude"
        result = subprocess.run(
            ["docker", "volume", "rm", vol_name],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"Removed volume '{vol_name}' for '{name}'.")
        else:
            print(f"Volume '{vol_name}' not found or in use.")
