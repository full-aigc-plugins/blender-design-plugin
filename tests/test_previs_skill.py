"""Structural tests for the blender-previs Skill.

The previs Skill is a contract carrier: its schemas and handoff template are what
downstream Dreamina/Seedance Skills consume. These tests pin the contract shape —
frontmatter identity, schema validity, example conformance, and the mandatory
"encoding.doesNotEncode" guard — with a stdlib-only checker so CI needs no extra
dependency. When jsonschema is installed, the same examples are checked against the
real 2020-12 validator as well; a stdlib check alone proves less than the real one.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "blender-previs"

try:
    import jsonschema

    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover - depends on the environment
    HAVE_JSONSCHEMA = False


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def check(instance, schema, errors, path="$"):
    """Minimal draft-2020-12 subset validator: types, required, enum, const, pattern."""
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']!r}")
    if "pattern" in schema and isinstance(instance, str) and not re.search(
        schema["pattern"], instance
    ):
        errors.append(f"{path}: {instance!r} does not match {schema['pattern']!r}")
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(instance, dict):
            errors.append(f"{path}: expected object")
            return
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required {key!r}")
        if schema.get("additionalProperties") is False:
            extra = set(instance) - set(schema.get("properties", {}))
            if extra:
                errors.append(f"{path}: additional properties {sorted(extra)}")
        for key, sub in schema.get("properties", {}).items():
            if key in instance:
                check(instance[key], sub, errors, f"{path}.{key}")
    elif expected == "array":
        if not isinstance(instance, list):
            errors.append(f"{path}: expected array")
            return
        if len(instance) < schema.get("minItems", 0):
            errors.append(f"{path}: fewer than minItems")
        for i, item in enumerate(instance):
            if "items" in schema:
                check(item, schema["items"], errors, f"{path}[{i}]")
    elif expected == "string" and not isinstance(instance, str):
        errors.append(f"{path}: expected string")
    elif expected == "integer" and not isinstance(instance, int):
        errors.append(f"{path}: expected integer")
    elif expected == "number" and not isinstance(instance, (int, float)):
        errors.append(f"{path}: expected number")


class PrevisSkillContractTests(unittest.TestCase):
    def setUp(self):
        self.skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    def test_frontmatter_name_matches_directory(self):
        match = re.search(r"^name: (\S+)$", self.skill, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), SKILL_DIR.name)

    def test_description_is_a_single_line(self):
        block = self.skill.split("---")[1]
        self.assertEqual(
            len(re.findall(r"^description:", block, re.MULTILINE)),
            1,
            "exactly one description key is allowed",
        )
        self.assertIsNone(
            re.search(r"^description: [|>]", block, re.MULTILINE),
            "block scalar descriptions are banned",
        )
        for line in block.splitlines():
            self.assertFalse(
                line.startswith(" ") and not line.startswith("  "),
                "continuation lines would make the description multi-line",
            )

    def test_references_all_linked_files_exist(self):
        for link in re.findall(r"\((references/[^)]+)\)", self.skill):
            self.assertTrue((SKILL_DIR / link).is_file(), f"missing {link}")

    def test_shot_table_example_conforms_to_schema(self):
        schema = load(SKILL_DIR / "references" / "previs-shot-table.schema.json")
        example = {
            "schema_version": "1.0",
            "project": {
                "id": "demo-chase",
                "title": "Rooftop chase",
                "fps": {"num": 24, "den": 1},
                "totalFrames": 168,
            },
            "roles": [
                {
                    "roleId": "heroine",
                    "label": "heroine",
                    "primitive": {"type": "cube", "colorHex": "#7FD4C1"},
                }
            ],
            "shots": [
                {
                    "shotId": "shot-01",
                    "startFrame": 1,
                    "durationFrames": 168,
                    "shotSize": "wide",
                    "camera": {
                        "positionMeters": [0, -8, 2],
                        "lookAtMeters": [0, 0, 1],
                        "move": "static",
                    },
                    "subjects": [
                        {"roleId": "heroine", "positionMeters": [0, 0, 1]}
                    ],
                }
            ],
        }
        errors = []
        check(example, schema, errors)
        self.assertEqual(errors, [])
        if HAVE_JSONSCHEMA:
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.validate(example, schema)

    def test_previs_map_example_conforms_and_guards_semantics(self):
        schema = load(SKILL_DIR / "references" / "previs-map.schema.json")
        example = {
            "schema_version": "1.0",
            "projectId": "demo-chase",
            "previsVideo": {
                "path": "out/previs.mp4",
                "durationFrames": 168,
                "fps": {"num": 24, "den": 1},
            },
            "cast": [
                {
                    "roleId": "heroine",
                    "label": "heroine",
                    "placeholder": {
                        "objectName": "previs_role_heroine",
                        "primitiveType": "cube",
                        "colorHex": "#7FD4C1",
                    },
                    "representsInFinal": "the heroine",
                }
            ],
            "encoding": {
                "encodes": [
                    "camera-movement",
                    "shot-size",
                    "cut-timing",
                    "subject-position",
                ],
                "doesNotEncode": ["limb-articulation"],
            },
        }
        errors = []
        check(example, schema, errors)
        self.assertEqual(errors, [])
        if HAVE_JSONSCHEMA:
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.validate(example, schema)

    def test_encoding_guard_is_enforced_by_schema(self):
        """A map that omits doesNotEncode must fail: geometry ≠ performance is the point."""
        schema = load(SKILL_DIR / "references" / "previs-map.schema.json")
        missing = {
            "schema_version": "1.0",
            "projectId": "x",
            "previsVideo": {
                "path": "p",
                "durationFrames": 1,
                "fps": {"num": 24, "den": 1},
            },
            "cast": [
                {
                    "roleId": "r",
                    "label": "r",
                    "placeholder": {
                        "objectName": "previs_role_r",
                        "primitiveType": "cube",
                        "colorHex": "#111111",
                    },
                    "representsInFinal": "r",
                }
            ],
            "encoding": {"encodes": ["cut-timing"]},
        }
        errors = []
        check(missing, schema, errors)
        self.assertTrue(any("doesNotEncode" in e for e in errors))

    def test_handoff_template_states_the_semantics_boundary(self):
        template = (
            SKILL_DIR / "references" / "seedance-handoff-prompt.md"
        ).read_text(encoding="utf-8")
        for phrase in (
            "严格参考白模视频中的摄影机运动、景别、切镜时间、人物整体位置和空间关系",
            "几何体只代表人物的位置和移动方向，不代表真实肢体动作",
            "camera movement, shot sizes, cut timings",
            "never real limb motion",
        ):
            self.assertIn(phrase, template)

    def test_skill_never_submits_paid_generation(self):
        self.assertIn("Never submit a paid video-generation request", self.skill)


if __name__ == "__main__":
    unittest.main()
