"""Release channels must be explicit and packages must exclude private files."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location(
    "release_tools", Path(__file__).resolve().parents[1] / "scripts/release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.component = self.root / release.COMPONENT
        (self.component / "frontend").mkdir(parents=True)

    def prepare(self, version):
        (self.component / "manifest.json").write_text(json.dumps({"version": version}))
        (self.root / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## [{version}] - 2026-10-18\n\nBeta notes.\n\n## [1.7.0] - 2026-10-17\nOld release.\n"
        )

    def test_stable_alpha_beta_rc_classification_and_exact_notes(self):
        for version, expected in [
            ("1.7.0", False),
            ("2.0.0b1", True),
            ("2.0.0a2", True),
            ("2.0.0rc1", True),
            ("2.0.0-rc1", True),
            ("2.0.0", False),
        ]:
            with self.subTest(version=version):
                self.prepare(version)
                result = release.metadata(self.root, "v" + version)
                self.assertEqual(result["prerelease"], expected)
                self.assertEqual(result["notes"], "Beta notes.\n")

    def test_invalid_tag_mismatch_and_missing_notes_stop_release(self):
        self.prepare("2.0.0b1")
        for tag in ["2.0.0b1", "v2.0.0-beta.1", "v2.0.0", "v02.0.0b1", "v2.0.0b1\n", "v2.0.0-rc0"]:
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release.metadata(self.root, tag)
        (self.root / "CHANGELOG.md").write_text("## [2.0.0b1] - 2026-10-18\n\n")
        with self.assertRaises(ValueError):
            release.metadata(self.root, "v2.0.0b1")

    def test_explicit_regular_rc_channel_is_scoped_to_exact_version(self):
        self.prepare("2.0.0-rc2")
        policy = self.root / ".github/release-channel.json"
        policy.parent.mkdir()
        policy.write_text(json.dumps({"version": "2.0.0-rc2", "prerelease": False}))
        self.assertFalse(release.metadata(self.root, "v2.0.0-rc2")["prerelease"])
        for channel in (
            {"version": "2.0.0-rc3", "prerelease": False},
            {"version": "2.0.0-rc2", "prerelease": "false"},
            {"version": "2.0.0-rc2"},
            [],
        ):
            policy.write_text(json.dumps(channel))
            with self.subTest(channel=channel), self.assertRaises(ValueError):
                release.metadata(self.root, "v2.0.0-rc2")
        policy.unlink()
        self.assertTrue(release.metadata(self.root, "v2.0.0-rc2")["prerelease"])

    def test_stale_frontend_module_stops_release(self):
        self.prepare("2.0.0b1")
        path = self.component / "frontend/account-loader.js"
        path.write_text('import("./account-workspace-card.js?v=1.8.0b21");')
        with self.assertRaises(ValueError):
            release.metadata(self.root, "v2.0.0b1")
        path.write_text('import("./account-workspace-card.js?v=2.0.0b1");')
        self.assertTrue(release.metadata(self.root, "v2.0.0b1")["prerelease"])

    def test_release_documentation_links_point_to_the_tag(self):
        self.prepare("2.0.0-rc1")
        path = self.root / "CHANGELOG.md"
        path.write_text(path.read_text().replace("Beta notes.", "[Upgrade](docs/UPGRADING.md)"))
        notes = release.metadata(self.root, "v2.0.0-rc1")["notes"]
        self.assertIn("/blob/v2.0.0-rc1/docs/UPGRADING.md)", notes)

    def test_archive_excludes_untracked_secrets_and_has_correct_root(self):
        self.prepare("2.0.0b1")
        names = [
            "manifest.json",
            "LICENSE",
            "NOTICE",
            "THIRD_PARTY_NOTICES.md",
            "__init__.py",
            "services.yaml",
        ]
        for name in names[1:]:
            (self.component / name).write_text("public")
        (self.component / "secrets.yaml").write_text("not for publication")
        tracked = (
            b"\0".join(str(release.COMPONENT / name).encode() for name in names) + b"\0"
        )
        archive = self.root / "dtek_monitor.zip"
        with patch.object(release.subprocess, "check_output", return_value=tracked):
            release.package(self.root, archive)
        with ZipFile(archive) as package:
            self.assertEqual(set(package.namelist()), set(names))
        # Permit the public HA action definitions, not arbitrary YAML configs.
        with patch.object(release.subprocess, "check_output", return_value=tracked +
                          str(release.COMPONENT / "secrets.yaml").encode() + b"\0"):
            with self.assertRaises(ValueError):
                release.package(self.root, archive)
