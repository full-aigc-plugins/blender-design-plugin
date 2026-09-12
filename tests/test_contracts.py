"""Contract tests for codex-blender plugin manifest and receipt schemas.

These tests MUST fail before implementation (RED) and pass after (GREEN).
"""

import json
import os
import sys
import unittest

# Ensure scripts/ is importable when running as `python3 -m unittest tests.test_contracts`
_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from validate_document import validate_document

_REPO_ROOT = os.path.dirname(os.path.dirname(__file__))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_SCENE_RECEIPT = {
    "schemaVersion": "codex-blender.receipt/v1",
    "producer": {"name": "codex-blender", "version": "0.1.0"},
    "blenderVersion": "4.2.0",
    "projectFingerprint": "aabbccdd11223344",
    "cameras": ["Camera.Main", "Camera.Overhead"],
    "frameRange": {"start": 1, "end": 250},
    "resolution": {"width": 1920, "height": 1080},
    "previewModes": ["white_model", "material_preview"],
    "warnings": [],
}

VALID_ARTIFACT_RECEIPT = {
    "schemaVersion": "codex-blender.receipt/v1",
    "producer": {"name": "codex-blender", "version": "0.1.0"},
    "path": "/tmp/preview.mp4",
    "sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
    "codec": "h264",
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "durationSeconds": 8.33,
    "bytes": 1048576,
    "camera": "Camera.Main",
    "frameRange": {"start": 1, "end": 250},
    "previewMode": "white_model",
    "restoration": {"status": "confirmed"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _SchemaTestBase(unittest.TestCase):
    """Common helpers for schema validation tests."""

    def _validate(self, schema_name: str, payload: dict) -> list[str]:
        return validate_document(schema_name, payload)

    def _assert_valid(self, schema_name: str, payload: dict):
        errors = self._validate(schema_name, payload)
        self.assertEqual(errors, [], f"Expected no errors but got: {errors}")

    def _assert_invalid(self, schema_name: str, payload: dict, msg: str = ""):
        errors = self._validate(schema_name, payload)
        self.assertGreater(len(errors), 0, f"Expected errors but got none. {msg}")


# ===========================================================================
# A. Plugin manifest
# ===========================================================================

class TestPluginManifest(unittest.TestCase):

    def test_plugin_json_exists(self):
        path = os.path.join(_REPO_ROOT, ".codex-plugin", "plugin.json")
        self.assertTrue(os.path.isfile(path), f"Missing {path}")

    def test_required_fields_present(self):
        path = os.path.join(_REPO_ROOT, ".codex-plugin", "plugin.json")
        with open(path) as f:
            data = json.load(f)
        # The Codex manifest schema (codex-rs/core-plugins/src/manifest.rs).
        required = ["name", "version", "description", "skills"]
        for field in required:
            self.assertIn(field, data, f"plugin.json missing required field: {field}")

    def test_declares_no_meaningless_fields(self):
        """Extra metadata keys are tolerated by Codex, but these two are meaningless.

        Codex's RawPluginManifest has no `deny_unknown_fields`, so `author`,
        `license`, `repository` and `homepage` are accepted (and ignored) — they
        are conventional metadata, not errors. `id` and `entryPoint` are not
        conventions of this ecosystem, so their presence would be noise.
        """
        path = os.path.join(_REPO_ROOT, ".codex-plugin", "plugin.json")
        with open(path) as f:
            data = json.load(f)
        for meaningless in ("id", "entryPoint"):
            self.assertNotIn(meaningless, data,
                             f"{meaningless} is not a Codex manifest field or convention")

    def test_display_name_is_in_interface(self):
        path = os.path.join(_REPO_ROOT, ".codex-plugin", "plugin.json")
        with open(path) as f:
            data = json.load(f)
        self.assertTrue(data.get("interface", {}).get("displayName"))

    def test_default_prompt_within_documented_limits(self):
        """Codex supports at most 3 prompts of at most 128 characters each."""
        path = os.path.join(_REPO_ROOT, ".codex-plugin", "plugin.json")
        with open(path) as f:
            data = json.load(f)
        prompts = data.get("interface", {}).get("defaultPrompt")
        if prompts is None:
            return
        if isinstance(prompts, str):
            prompts = [prompts]
        self.assertLessEqual(len(prompts), 3, "at most 3 default prompts are supported")
        for prompt in prompts:
            self.assertLessEqual(len(prompt), 128,
                                 f"default prompt exceeds 128 characters: {prompt!r}")

    def test_name_is_a_valid_identifier_segment(self):
        """Codex rejects a display name here; it belongs in interface.displayName."""
        path = os.path.join(_REPO_ROOT, ".codex-plugin", "plugin.json")
        with open(path) as f:
            data = json.load(f)
        name = data["name"]
        self.assertRegex(name, r"^[A-Za-z0-9._-]+$",
                         "plugin name allows only ASCII letters, digits, `.`, `_`, `-`")
        self.assertNotIn(" ", name)

    def test_skills_path_uses_required_relative_form(self):
        path = os.path.join(_REPO_ROOT, ".codex-plugin", "plugin.json")
        with open(path) as f:
            data = json.load(f)
        skills = data["skills"]
        paths = [skills] if isinstance(skills, str) else skills
        for raw in paths:
            self.assertTrue(raw.startswith("./"), f"{raw} must start with `./`")
            self.assertNotEqual(raw, "./", "path must not be `./`")
            self.assertNotIn("..", raw.split("/"), "path must not contain `..`")


# ===========================================================================
# B. Scene receipt schema — positive path
# ===========================================================================

class TestSceneReceiptValid(_SchemaTestBase):

    def test_valid_minimal(self):
        self._assert_valid("scene_receipt", VALID_SCENE_RECEIPT)

    def test_empty_cameras_and_warnings(self):
        payload = {**VALID_SCENE_RECEIPT, "cameras": [], "warnings": []}
        self._assert_valid("scene_receipt", payload)


# ===========================================================================
# C. Scene receipt schema — closed schema (additionalProperties: false)
# ===========================================================================

class TestSceneReceiptRejectsUnknownFields(_SchemaTestBase):

    def test_unknown_top_level_field_rejected(self):
        payload = {**VALID_SCENE_RECEIPT, "extraField": "should not be here"}
        self._assert_invalid("scene_receipt", payload)

    def test_unknown_nested_in_producer_rejected(self):
        payload = {**VALID_SCENE_RECEIPT}
        payload["producer"] = {**VALID_SCENE_RECEIPT["producer"], "bogus": 1}
        self._assert_invalid("scene_receipt", payload)

    def test_unknown_nested_in_resolution_rejected(self):
        payload = {**VALID_SCENE_RECEIPT}
        payload["resolution"] = {**VALID_SCENE_RECEIPT["resolution"], "dpi": 300}
        self._assert_invalid("scene_receipt", payload)


# ===========================================================================
# C1. Schema version const enforcement
# ===========================================================================

class TestSchemaVersionConst(_SchemaTestBase):

    def test_wrong_schemaVersion_rejected_in_scene(self):
        payload = {**VALID_SCENE_RECEIPT, "schemaVersion": "wrong-version"}
        self._assert_invalid("scene_receipt", payload)

    def test_wrong_schemaVersion_rejected_in_artifact(self):
        payload = {**VALID_ARTIFACT_RECEIPT, "schemaVersion": "wrong-version"}
        self._assert_invalid("artifact_receipt", payload)


# ===========================================================================
# C2. Scene receipt schema — missing required fields
# ===========================================================================

class TestSceneReceiptMissingFields(_SchemaTestBase):

    def _drop(self, field: str) -> dict:
        return {k: v for k, v in VALID_SCENE_RECEIPT.items() if k != field}

    def test_missing_blenderVersion_rejected(self):
        self._assert_invalid("scene_receipt", self._drop("blenderVersion"))

    def test_missing_producer_rejected(self):
        self._assert_invalid("scene_receipt", self._drop("producer"))

    def test_missing_frameRange_rejected(self):
        self._assert_invalid("scene_receipt", self._drop("frameRange"))

    def test_missing_resolution_rejected(self):
        self._assert_invalid("scene_receipt", self._drop("resolution"))


# ===========================================================================
# D. Artifact receipt schema — positive path
# ===========================================================================

class TestArtifactReceiptValid(_SchemaTestBase):

    def test_valid_minimal(self):
        self._assert_valid("artifact_receipt", VALID_ARTIFACT_RECEIPT)


# ===========================================================================
# E. Artifact receipt schema — closed schema
# ===========================================================================

class TestArtifactReceiptRejectsUnknownFields(_SchemaTestBase):

    def test_unknown_top_level_field_rejected(self):
        payload = {**VALID_ARTIFACT_RECEIPT, "extraField": True}
        self._assert_invalid("artifact_receipt", payload)

    def test_unknown_nested_in_restoration_rejected(self):
        payload = {**VALID_ARTIFACT_RECEIPT}
        payload["restoration"] = {"status": "confirmed", "verified": True}
        self._assert_invalid("artifact_receipt", payload)


# ===========================================================================
# E2. Artifact receipt schema — missing required fields
# ===========================================================================

class TestArtifactReceiptMissingFields(_SchemaTestBase):

    def _drop(self, field: str) -> dict:
        return {k: v for k, v in VALID_ARTIFACT_RECEIPT.items() if k != field}

    def test_missing_sha256_rejected(self):
        self._assert_invalid("artifact_receipt", self._drop("sha256"))

    def test_missing_path_rejected(self):
        self._assert_invalid("artifact_receipt", self._drop("path"))

    def test_missing_restoration_rejected(self):
        self._assert_invalid("artifact_receipt", self._drop("restoration"))

    def test_missing_codec_rejected(self):
        self._assert_invalid("artifact_receipt", self._drop("codec"))


# ===========================================================================
# F. SHA-256 validation
# ===========================================================================

class TestSha256Validation(_SchemaTestBase):

    def test_sha256_must_be_64_hex_chars(self):
        payload = {**VALID_ARTIFACT_RECEIPT, "sha256": "abc123"}
        self._assert_invalid("artifact_receipt", payload)

    def test_sha256_uppercase_rejected(self):
        sha = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
        payload = {**VALID_ARTIFACT_RECEIPT, "sha256": sha}
        self._assert_invalid("artifact_receipt", payload)


# ===========================================================================
# G. Media dimensions — positive integers
# ===========================================================================

class TestMediaDimensionValidation(_SchemaTestBase):

    def test_zero_width_rejected(self):
        payload = {**VALID_ARTIFACT_RECEIPT, "width": 0}
        self._assert_invalid("artifact_receipt", payload)

    def test_negative_height_rejected(self):
        payload = {**VALID_ARTIFACT_RECEIPT, "height": -1}
        self._assert_invalid("artifact_receipt", payload)


# ===========================================================================
# H. Restoration status enum
# ===========================================================================

class TestRestorationStatusValidation(_SchemaTestBase):

    def test_invalid_status_rejected(self):
        payload = {**VALID_ARTIFACT_RECEIPT, "restoration": {"status": "partial"}}
        self._assert_invalid("artifact_receipt", payload)

    def test_each_valid_status(self):
        for status in ("confirmed", "failed", "unknown"):
            payload = {**VALID_ARTIFACT_RECEIPT, "restoration": {"status": status}}
            self._assert_valid("artifact_receipt", payload)


# ===========================================================================
# I. Distribution validator
# ===========================================================================

class TestDistributionValidator(unittest.TestCase):

    def test_validator_script_exists(self):
        path = os.path.join(_REPO_ROOT, "scripts", "validate_distribution.py")
        self.assertTrue(os.path.isfile(path), f"Missing {path}")

    def test_validator_runs_clean(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(_REPO_ROOT, "scripts", "validate_distribution.py")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"Validator failed:\n{result.stdout}\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
