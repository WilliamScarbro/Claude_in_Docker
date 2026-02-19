# SPDX-License-Identifier: BUSL-1.1
"""skua restart — restart a project container."""

from types import SimpleNamespace

from skua.commands.run import cmd_run
from skua.commands.stop import cmd_stop


def cmd_restart(args):
    name = str(getattr(args, "name", "") or "").strip()
    force = bool(getattr(args, "force", False))
    if not name:
        print("Error: Provide a project name.")
        return
    if not cmd_stop(SimpleNamespace(name=name, force=force)):
        return
    cmd_run(SimpleNamespace(name=name))
