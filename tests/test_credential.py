# SPDX-License-Identifier: BUSL-1.1
"""Tests for credential source resolution."""

import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

# Ensure the skua package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skua.commands.credential import _any_auth_files_present, resolve_credential_sources
from skua.config.resources import AgentAuthSpec, AgentConfig


class TestCredentialSourceResolution(unittest.TestCase):
    @staticmethod
    def _claude_agent() -> AgentConfig:
        return AgentConfig(
            name="claude",
            auth=AgentAuthSpec(
                dir=".claude",
                files=[".credentials.json", ".claude.json"],
            ),
        )

    @mock.patch("skua.commands.credential.Path.home")
    def test_resolve_sources_falls_back_to_home_for_claude_json(self, mock_home):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "home"
            (home / ".claude").mkdir(parents=True)
            (home / ".claude" / ".credentials.json").write_text('{"token":"abc"}')
            (home / ".claude.json").write_text("{}")
            mock_home.return_value = home

            sources = resolve_credential_sources(None, self._claude_agent())
            by_dest = {dest: src for src, dest in sources}

            self.assertEqual(
                by_dest[".credentials.json"],
                home / ".claude" / ".credentials.json",
            )
            self.assertEqual(
                by_dest[".claude.json"],
                home / ".claude.json",
            )

    @mock.patch("skua.commands.credential.Path.home")
    def test_resolve_sources_prefers_auth_dir_first(self, mock_home):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "home"
            (home / ".claude").mkdir(parents=True)
            (home / ".claude" / ".credentials.json").write_text('{"token":"abc"}')
            (home / ".claude" / ".claude.json").write_text('{"from":"auth-dir"}')
            (home / ".claude.json").write_text('{"from":"home-root"}')
            mock_home.return_value = home

            sources = resolve_credential_sources(None, self._claude_agent())
            by_dest = {dest: src for src, dest in sources}

            self.assertEqual(
                by_dest[".claude.json"],
                home / ".claude" / ".claude.json",
            )

    @mock.patch("skua.commands.credential.Path.home")
    def test_any_auth_files_present_includes_home_root_fallback(self, mock_home):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "home"
            (home / ".claude").mkdir(parents=True)
            (home / ".claude.json").write_text("{}")
            mock_home.return_value = home

            self.assertTrue(
                _any_auth_files_present(home / ".claude", [".claude.json"], self._claude_agent())
            )
