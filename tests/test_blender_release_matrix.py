"""Tests for the Blender release matrix config and updater.

All tests are offline. The updater's fetcher is injectable so tests drive it
with the real 4.2.23 content as a fixture.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "blender-release-matrix.json"

# Real content fetched from download.blender.org for 4.2.23.
REAL_4_2_23_SHA256 = (
    "8b6bc5fafd4773e94bb863ca19ba1c9a54d096eecbbc4375eae7dbc3b49fab40  blender-4.2.23-macos-arm64.dmg\n"
    "c85e18c5d4bd5fe94a43414409ebe4bbc0139ad67a14b2db584b0fcbd67b77b6  blender-4.2.23-macos-x64.dmg\n"
    "bea0eb3146be13eae6225409a117b215184f41b7f79e799f97cb3abb8f6dc404  blender-4.2.23-linux-x64.tar.xz\n"
    "243025ed0aad3d9d537f3d58dbf3da2ba55f8251560d3e8ddccbfdb66a6817e5  blender-4.2.23-windows-x64.msi\n"
    "b0ff496299bf3323bf63e3ddb82a4a8dd93c9a5dd50e404e0e7549a1ee61f609  blender-4.2.23-windows-x64.msix\n"
    "82e791475779a7342424a480bdde9a20b43710da9264c60346125aa16cd910cb  blender-4.2.23-windows-x64.zip\n"
)

EXPECTED_VERSIONS = [
    ("4.2.23", "Blender4.2"),
    ("4.3.2", "Blender4.3"),
    ("4.4.3", "Blender4.4"),
    ("4.5.13", "Blender4.5"),
    ("5.0.1", "Blender5.0"),
    ("5.1.2", "Blender5.1"),
    ("5.2.1", "Blender5.2"),
]

EXPECTED_PLATFORMS = ["macos-arm64", "windows-x64"]

ARTIFACT_TEMPLATES = {
    "macos-arm64": "blender-{ver}-macos-arm64.dmg",
    "windows-x64": "blender-{ver}-windows-x64.zip",
}


class TestMatrixConfig(unittest.TestCase):
    """Validate the shape and content of blender-release-matrix.json."""

    def setUp(self):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            self.config = json.load(f)

    def test_has_combinations_key(self):
        self.assertIn("combinations", self.config)
        self.assertIsInstance(self.config["combinations"], list)

    def test_exactly_14_combinations(self):
        self.assertEqual(len(self.config["combinations"]), 14)

    def test_each_combination_has_required_fields(self):
        for combo in self.config["combinations"]:
            with self.subTest(combo=combo):
                for field in ("version", "platform", "url", "artifact", "sha256"):
                    self.assertIn(field, combo, f"missing {field} in {combo}")

    def test_sha256_format(self):
        for combo in self.config["combinations"]:
            with self.subTest(combo=combo):
                sha = combo["sha256"]
                self.assertEqual(len(sha), 64, f"SHA-256 length != 64: {sha}")
                self.assertTrue(
                    all(c in "0123456789abcdef" for c in sha),
                    f"SHA-256 not lowercase hex: {sha}",
                )

    def test_url_format(self):
        for combo in self.config["combinations"]:
            with self.subTest(combo=combo):
                url = combo["url"]
                self.assertTrue(
                    url.startswith("https://download.blender.org/release/Blender"),
                    f"unexpected URL prefix: {url}",
                )

    def test_artifact_names_match_versions(self):
        for combo in self.config["combinations"]:
            with self.subTest(combo=combo):
                ver = combo["version"]
                platform = combo["platform"]
                expected = ARTIFACT_TEMPLATES[platform].format(ver=ver)
                self.assertEqual(
                    combo["artifact"], expected,
                    f"artifact mismatch for {ver}/{platform}",
                )

    def test_all_versions_present(self):
        versions = {c["version"] for c in self.config["combinations"]}
        for ver, _dir in EXPECTED_VERSIONS:
            self.assertIn(ver, versions, f"missing version {ver}")

    def test_all_platforms_present_for_each_version(self):
        for combo in self.config["combinations"]:
            with self.subTest(combo=combo):
                self.assertIn(combo["platform"], EXPECTED_PLATFORMS)

    def test_no_duplicate_version_platform(self):
        pairs = [(c["version"], c["platform"]) for c in self.config["combinations"]]
        self.assertEqual(len(pairs), len(set(pairs)), "duplicate version/platform pair found")

    def test_blender_directory_in_url(self):
        for combo in self.config["combinations"]:
            with self.subTest(combo=combo):
                ver = combo["version"]
                # Find the expected Blender dir for this version
                expected_dir = None
                for v, d in EXPECTED_VERSIONS:
                    if v == ver:
                        expected_dir = d
                        break
                self.assertIn(
                    f"/{expected_dir}/", combo["url"],
                    f"URL missing /{expected_dir}/ for version {ver}",
                )


class TestMatrixKnownChecksums(unittest.TestCase):
    """Cross-validate specific checksums against ground truth."""

    def setUp(self):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            self.config = json.load(f)
        self._index = {
            (c["version"], c["platform"]): c for c in self.config["combinations"]
        }

    def test_5_2_1_windows_matches_ci_workflow(self):
        """The 5.2.1 Windows SHA was independently verified by CI."""
        combo = self._index[("5.2.1", "windows-x64")]
        self.assertEqual(
            combo["sha256"],
            "0e631dad7d0cad6d5d18abdd2e2550f6c0213215334eda00ddbd3d22b96ecb2c",
        )

    def test_4_2_23_macos_arm64(self):
        combo = self._index[("4.2.23", "macos-arm64")]
        self.assertEqual(
            combo["sha256"],
            "8b6bc5fafd4773e94bb863ca19ba1c9a54d096eecbbc4375eae7dbc3b49fab40",
        )

    def test_4_2_23_windows_x64(self):
        combo = self._index[("4.2.23", "windows-x64")]
        self.assertEqual(
            combo["sha256"],
            "82e791475779a7342424a480bdde9a20b43710da9264c60346125aa16cd910cb",
        )


class TestUpdater(unittest.TestCase):
    """Test the updater script with an injectable fetcher (offline)."""

    def _make_updater(self):
        """Import the updater module."""
        import importlib
        import sys
        # Ensure scripts/ is importable
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import update_blender_release_matrix as updater
        return updater

    def test_parse_sha256_lines_normal(self):
        updater = self._make_updater()
        entries = updater.parse_sha256_content(REAL_4_2_23_SHA256)
        # Should parse all6 lines
        self.assertEqual(len(entries), 6)
        # Check one specific entry
        dmg = [e for e in entries if e.filename.endswith("macos-arm64.dmg")]
        self.assertEqual(len(dmg), 1)
        self.assertEqual(
            dmg[0].sha256,
            "8b6bc5fafd4773e94bb863ca19ba1c9a54d096eecbbc4375eae7dbc3b49fab40",
        )

    def test_parse_sha256_extracts_correct_artifacts(self):
        updater = self._make_updater()
        entries = updater.parse_sha256_content(REAL_4_2_23_SHA256)
        filenames = {e.filename for e in entries}
        self.assertIn("blender-4.2.23-macos-arm64.dmg", filenames)
        self.assertIn("blender-4.2.23-windows-x64.zip", filenames)

    def test_missing_artifact_raises(self):
        """If a required artifact is missing, the updater must fail."""
        updater = self._make_updater()
        # Content with no windows-x64.zip line
        incomplete = (
            "8b6bc5fafd4773e94bb863ca19ba1c9a54d096eecbbc4375eae7dbc3b49fab40  "
            "blender-4.2.23-macos-arm64.dmg\n"
        )
        with self.assertRaises(updater.MissingArtifactError):
            updater.parse_sha256_content(
                incomplete,
                required_artifacts=["blender-4.2.23-macos-arm64.dmg", "blender-4.2.23-windows-x64.zip"],
            )

    def test_malformed_line_raises(self):
        """A line that doesn't match the sha256sum format must fail."""
        updater = self._make_updater()
        malformed = "not-a-hash  blender-4.2.23-macos-arm64.dmg\n"
        with self.assertRaises(updater.MalformedLineError):
            updater.parse_sha256_content(malformed)

    def test_short_hash_raises(self):
        """A hash shorter than64 hex chars must fail."""
        updater = self._make_updater()
        short = "8b6bc5f  blender-4.2.23-macos-arm64.dmg\n"
        with self.assertRaises(updater.MalformedLineError):
            updater.parse_sha256_content(short)

    def test_wrong_filename_raises(self):
        """An unexpected filename (not matching the expected pattern) must fail."""
        updater = self._make_updater()
        wrong = "8b6bc5fafd4773e94bb863ca19ba1c9a54d096eecbbc4375eae7dbc3b49fab40  blender-4.2.23-linux-x64.tar.xz\n"
        with self.assertRaises(updater.MissingArtifactError):
            updater.parse_sha256_content(
                wrong,
                required_artifacts=["blender-4.2.23-macos-arm64.dmg", "blender-4.2.23-windows-x64.zip"],
            )

    def test_update_matrix_uses_fetcher(self):
        """The updater calls the injected fetcher and updates config entries."""
        updater = self._make_updater()

        def fake_fetcher(version, blender_dir):
            if version == "4.2.23":
                return REAL_4_2_23_SHA256
            raise AssertionError(f"unexpected fetch for {version}")

        # Load a fresh config and run update with a subset
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)

        # Only update 4.2.23 entries
        subset = [c for c in config["combinations"] if c["version"] == "4.2.23"]
        updater.update_combinations(subset, fetcher=fake_fetcher)

        macos = [c for c in subset if c["platform"] == "macos-arm64"][0]
        self.assertEqual(
            macos["sha256"],
            "8b6bc5fafd4773e94bb863ca19ba1c9a54d096eecbbc4375eae7dbc3b49fab40",
        )
        windows = [c for c in subset if c["platform"] == "windows-x64"][0]
        self.assertEqual(
            windows["sha256"],
            "82e791475779a7342424a480bdde9a20b43710da9264c60346125aa16cd910cb",
        )


if __name__ == "__main__":
    unittest.main()
