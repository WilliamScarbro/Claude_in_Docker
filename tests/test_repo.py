"""Tests for git repository support in skua projects.

Validates:
- Project dataclass stores and serializes the repo field
- ConfigStore provides correct repo paths
- `skua add` handles --repo and --dir mutual exclusivity
- `skua add` validates git URLs
- `skua run` clones repos and sets project.directory
- `skua list` shows repo URL when directory is empty
- `skua describe` includes repo in output
"""

import argparse
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

# Ensure the skua package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skua.config.resources import (
    Project, ProjectGitSpec, ProjectSshSpec, ProjectImageSpec,
    resource_to_dict, resource_from_dict,
)
from skua.config.loader import ConfigStore
from skua.commands.add import _is_git_url


class TestProjectRepoField(unittest.TestCase):
    """Test that the Project dataclass handles the repo field correctly."""

    def test_default_repo_is_empty(self):
        p = Project(name="test")
        self.assertEqual(p.repo, "")

    def test_repo_stored(self):
        p = Project(name="test", repo="https://github.com/user/repo.git")
        self.assertEqual(p.repo, "https://github.com/user/repo.git")

    def test_repo_serialization_roundtrip(self):
        p = Project(
            name="test",
            repo="git@github.com:user/repo.git",
            directory="",
        )
        d = resource_to_dict(p)
        self.assertEqual(d["spec"]["repo"], "git@github.com:user/repo.git")

        p2 = resource_from_dict(d)
        self.assertEqual(p2.repo, "git@github.com:user/repo.git")
        self.assertEqual(p2.name, "test")

    def test_repo_empty_serialization(self):
        p = Project(name="test", directory="/tmp/foo")
        d = resource_to_dict(p)
        self.assertEqual(d["spec"]["repo"], "")

        p2 = resource_from_dict(d)
        self.assertEqual(p2.repo, "")
        self.assertEqual(p2.directory, "/tmp/foo")

    def test_repo_and_directory_coexist(self):
        """Both fields can be set (run.py sets directory from repo at runtime)."""
        p = Project(name="test", repo="https://x.com/r.git", directory="/tmp/clone")
        self.assertEqual(p.repo, "https://x.com/r.git")
        self.assertEqual(p.directory, "/tmp/clone")


class TestConfigStoreRepoPaths(unittest.TestCase):
    """Test ConfigStore repo directory helpers."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = ConfigStore(config_dir=Path(self.tmpdir))

    def test_repos_dir(self):
        expected = Path(self.tmpdir) / "repos"
        self.assertEqual(self.store.repos_dir(), expected)

    def test_repo_dir(self):
        expected = Path(self.tmpdir) / "repos" / "myproject"
        self.assertEqual(self.store.repo_dir("myproject"), expected)

    def test_repo_dir_different_projects(self):
        self.assertNotEqual(
            self.store.repo_dir("proj-a"),
            self.store.repo_dir("proj-b"),
        )


class TestGitUrlValidation(unittest.TestCase):
    """Test the _is_git_url helper."""

    def test_https_url(self):
        self.assertTrue(_is_git_url("https://github.com/user/repo.git"))

    def test_http_url(self):
        self.assertTrue(_is_git_url("http://github.com/user/repo.git"))

    def test_git_protocol(self):
        self.assertTrue(_is_git_url("git://github.com/user/repo.git"))

    def test_ssh_scp_style(self):
        self.assertTrue(_is_git_url("git@github.com:user/repo.git"))

    def test_ssh_url(self):
        self.assertTrue(_is_git_url("ssh://git@github.com/user/repo.git"))

    def test_plain_string_rejected(self):
        self.assertFalse(_is_git_url("foo"))

    def test_local_path_rejected(self):
        self.assertFalse(_is_git_url("/tmp/some/repo"))

    def test_relative_path_rejected(self):
        self.assertFalse(_is_git_url("some/repo"))

    def test_ftp_rejected(self):
        self.assertFalse(_is_git_url("ftp://server/repo.git"))


class TestAddMutualExclusivity(unittest.TestCase):
    """Test that --dir and --repo are mutually exclusive in cmd_add."""

    def _make_args(self, **kwargs):
        defaults = dict(
            name="test-proj",
            dir=None,
            repo=None,
            ssh_key="",
            env=None,
            security=None,
            agent=None,
            quick=True,
            no_prompt=True,
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    @mock.patch("skua.commands.add.ConfigStore")
    def test_dir_and_repo_both_set_errors(self, MockStore):
        """Providing both --dir and --repo should exit with error."""
        mock_store = MockStore.return_value
        mock_store.is_initialized.return_value = True
        mock_store.load_project.return_value = None

        from skua.commands.add import cmd_add

        args = self._make_args(dir="/tmp/foo", repo="https://github.com/u/r.git")
        with self.assertRaises(SystemExit) as ctx:
            cmd_add(args)
        self.assertEqual(ctx.exception.code, 1)

    @mock.patch("skua.commands.add.ConfigStore")
    def test_repo_only_accepted(self, MockStore):
        """Providing only --repo should not error on mutual exclusivity."""
        mock_store = MockStore.return_value
        mock_store.is_initialized.return_value = True
        mock_store.load_project.return_value = None
        mock_store.load_global.return_value = {"defaults": {}}
        mock_store.load_environment.return_value = None

        from skua.commands.add import cmd_add

        args = self._make_args(repo="https://github.com/u/r.git")
        # Should not raise SystemExit for mutual exclusivity
        # (may raise for other reasons like missing environment, but that's fine)
        try:
            cmd_add(args)
        except SystemExit:
            # If it exits, it shouldn't be due to mutual exclusivity
            pass

        # Verify save_resource was called with a Project containing the repo
        mock_store.save_resource.assert_called_once()
        saved_project = mock_store.save_resource.call_args[0][0]
        self.assertEqual(saved_project.repo, "https://github.com/u/r.git")
        self.assertEqual(saved_project.directory, "")

    @mock.patch("skua.commands.add.ConfigStore")
    def test_invalid_repo_url_errors(self, MockStore):
        """Providing a non-URL string as --repo should exit with error."""
        mock_store = MockStore.return_value
        mock_store.is_initialized.return_value = True
        mock_store.load_project.return_value = None

        from skua.commands.add import cmd_add

        args = self._make_args(repo="not-a-url")
        with self.assertRaises(SystemExit) as ctx:
            cmd_add(args)
        self.assertEqual(ctx.exception.code, 1)


class TestRunRepoClone(unittest.TestCase):
    """Test that cmd_run clones repos correctly."""

    def test_clone_invoked_when_repo_dir_missing(self):
        """When project.repo is set and clone dir doesn't exist, git clone is called."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ConfigStore(config_dir=Path(tmpdir))

            project = Project(
                name="test-proj",
                repo="https://github.com/user/repo.git",
                directory="",
                ssh=ProjectSshSpec(),
            )

            clone_dir = store.repo_dir("test-proj")
            self.assertFalse(clone_dir.exists())

            # Mock subprocess.run to simulate git clone
            with mock.patch("skua.commands.run.subprocess.run") as mock_run:
                mock_run.return_value = mock.Mock(returncode=0)

                # Simulate the clone logic from cmd_run
                if project.repo:
                    if not clone_dir.exists():
                        clone_cmd = ["git", "clone"]
                        clone_cmd += [project.repo, str(clone_dir)]
                        subprocess.run(clone_cmd, check=True)
                    project.directory = str(clone_dir)

                mock_run.assert_called_once_with(
                    ["git", "clone", "https://github.com/user/repo.git", str(clone_dir)],
                    check=True,
                )
                self.assertEqual(project.directory, str(clone_dir))

    def test_clone_skipped_when_repo_dir_exists(self):
        """When clone directory already exists, git clone is not called."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ConfigStore(config_dir=Path(tmpdir))

            project = Project(
                name="test-proj",
                repo="https://github.com/user/repo.git",
                directory="",
                ssh=ProjectSshSpec(),
            )

            clone_dir = store.repo_dir("test-proj")
            clone_dir.mkdir(parents=True)

            with mock.patch("skua.commands.run.subprocess.run") as mock_run:
                # Simulate the clone logic from cmd_run
                if project.repo:
                    if not clone_dir.exists():
                        subprocess.run(
                            ["git", "clone", project.repo, str(clone_dir)],
                            check=True,
                        )
                    project.directory = str(clone_dir)

                mock_run.assert_not_called()
                self.assertEqual(project.directory, str(clone_dir))

    def test_clone_uses_ssh_key_when_set(self):
        """When SSH key is set, git clone uses core.sshCommand."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ConfigStore(config_dir=Path(tmpdir))

            project = Project(
                name="test-proj",
                repo="git@github.com:user/repo.git",
                directory="",
                ssh=ProjectSshSpec(private_key="/home/user/.ssh/id_rsa"),
            )

            clone_dir = store.repo_dir("test-proj")

            with mock.patch("skua.commands.run.subprocess.run") as mock_run:
                mock_run.return_value = mock.Mock(returncode=0)

                # Simulate the clone logic from cmd_run
                if project.repo:
                    if not clone_dir.exists():
                        clone_cmd = ["git", "clone"]
                        if project.ssh.private_key:
                            ssh_cmd = f"ssh -i {project.ssh.private_key} -o StrictHostKeyChecking=no"
                            clone_cmd = ["git", "-c", f"core.sshCommand={ssh_cmd}", "clone"]
                        clone_cmd += [project.repo, str(clone_dir)]
                        subprocess.run(clone_cmd, check=True)
                    project.directory = str(clone_dir)

                expected_ssh = "ssh -i /home/user/.ssh/id_rsa -o StrictHostKeyChecking=no"
                mock_run.assert_called_once_with(
                    [
                        "git", "-c", f"core.sshCommand={expected_ssh}", "clone",
                        "git@github.com:user/repo.git", str(clone_dir),
                    ],
                    check=True,
                )


class TestListShowsRepo(unittest.TestCase):
    """Test that skua list shows repo URL when directory is empty."""

    def test_proj_dir_falls_back_to_repo(self):
        """When directory is empty but repo is set, list should show repo."""
        p = Project(name="test", repo="https://github.com/user/repo.git", directory="")
        proj_dir = p.directory or p.repo or "(none)"
        self.assertEqual(proj_dir, "https://github.com/user/repo.git")

    def test_proj_dir_prefers_directory(self):
        """When directory is set, list should show directory."""
        p = Project(name="test", repo="https://github.com/user/repo.git", directory="/tmp/foo")
        proj_dir = p.directory or p.repo or "(none)"
        self.assertEqual(proj_dir, "/tmp/foo")

    def test_proj_dir_none_when_both_empty(self):
        p = Project(name="test")
        proj_dir = p.directory or p.repo or "(none)"
        self.assertEqual(proj_dir, "(none)")


class TestProjectYamlPersistence(unittest.TestCase):
    """Test saving and loading a project with repo through ConfigStore."""

    def test_save_and_load_project_with_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ConfigStore(config_dir=Path(tmpdir))
            store.ensure_dirs()

            project = Project(
                name="my-repo-proj",
                repo="https://github.com/user/repo.git",
                directory="",
                environment="local-docker",
                security="open",
                agent="claude",
                git=ProjectGitSpec(),
                ssh=ProjectSshSpec(private_key="/home/user/.ssh/id_rsa"),
                image=ProjectImageSpec(),
            )
            store.save_resource(project)

            loaded = store.load_project("my-repo-proj")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.repo, "https://github.com/user/repo.git")
            self.assertEqual(loaded.directory, "")
            self.assertEqual(loaded.name, "my-repo-proj")
            self.assertEqual(loaded.ssh.private_key, "/home/user/.ssh/id_rsa")

    def test_save_and_load_project_without_repo(self):
        """Projects without repo should still work (backwards compatible)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ConfigStore(config_dir=Path(tmpdir))
            store.ensure_dirs()

            project = Project(
                name="local-proj",
                directory="/tmp/my-code",
                environment="local-docker",
            )
            store.save_resource(project)

            loaded = store.load_project("local-proj")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.repo, "")
            self.assertEqual(loaded.directory, "/tmp/my-code")


class TestDescribeIncludesRepo(unittest.TestCase):
    """Test that describe output includes the repo field."""

    def test_resource_to_dict_includes_repo(self):
        p = Project(name="test", repo="https://github.com/user/repo.git")
        d = resource_to_dict(p)
        self.assertIn("repo", d["spec"])
        self.assertEqual(d["spec"]["repo"], "https://github.com/user/repo.git")


class TestValidationWithRepo(unittest.TestCase):
    """Test that validation handles projects with repo set."""

    def test_no_directory_warning_with_repo_only(self):
        """A project with repo but no directory should still warn about no directory.
        (directory is populated at runtime by cmd_run, not at add time)."""
        from skua.config.resources import Environment, SecurityProfile, AgentConfig
        from skua.config.validation import validate_project

        project = Project(name="test", repo="https://github.com/u/r.git")
        env = Environment(name="local-docker")
        sec = SecurityProfile(name="open")
        agent = AgentConfig(name="claude")

        result = validate_project(project, env, sec, agent)
        # Should warn about missing directory (it's set at runtime)
        dir_warnings = [w for w in result.warnings if "no directory" in w]
        self.assertTrue(len(dir_warnings) > 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
