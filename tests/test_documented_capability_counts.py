"""Documented capability counts must be generated, never hand-maintained.

The 0.3.x docs asserted a single merged figure ("163 tools: 136 L3, 3 L4, 24 L1,
22 Skills"). That number matched neither runtime mode and drifted silently
because nothing regenerated it.

These tests pin the rule from the 1.0 spec: Managed and Connector are counted
**separately**, every outward-facing number comes from the runtime registry, and
the numbers quoted in the docs are the generated ones.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

from scripts.harness.runtime_catalog import (
    generate_coverage_summary,
    generate_coverage_summaries,
)

ROOT = Path(__file__).resolve().parents[1]
COUNTS_PATH = ROOT / "docs/verification/capability-counts.json"
README = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"
COMPLETION_DOC = ROOT / "docs/verification/full-plan-completion.md"
MATRIX_DOC = ROOT / "docs/verification/blender-domain-coverage-matrix.md"
PROVENANCE_PATH = ROOT / "docs/verification/1.0-baseline-provenance.json"

MATURITIES = ("L1", "L2", "L3", "L4")


class CoverageSummaryTests(unittest.TestCase):
    """generate_coverage_summary() is the single source for these numbers."""

    def test_returns_per_mode_summary(self):
        summary = generate_coverage_summary("managed")
        self.assertEqual(summary["runtimeMode"], "managed")
        for key in ("commands", "domains", "skills"):
            self.assertIn(key, summary)
        for grade in MATURITIES:
            self.assertIn(grade, summary["commands"])

    def test_counts_are_internally_consistent(self):
        for mode in ("managed", "connector"):
            summary = generate_coverage_summary(mode)
            graded = sum(summary["commands"][g] for g in MATURITIES)
            self.assertEqual(
                graded, summary["commands"]["total"],
                f"{mode}: graded totals must sum to the command total",
            )

    def test_modes_are_not_merged_into_one_total(self):
        """The spec forbids a single combined command count."""
        summaries = generate_coverage_summaries()
        self.assertIn("managed", summaries)
        self.assertIn("connector", summaries)
        managed = summaries["managed"]["commands"]["total"]
        connector = summaries["connector"]["commands"]["total"]
        self.assertNotIn(
            "total", summaries,
            "no merged top-level total is allowed",
        )
        # The two modes may legitimately differ; assert they are reported apart.
        self.assertIsInstance(managed, int)
        self.assertIsInstance(connector, int)

    def test_connector_difference_is_reported(self):
        """The connector's extra commands must be itemised, not folded in."""
        summaries = generate_coverage_summaries()
        difference = summaries["modeDifference"]
        self.assertIn("onlyConnector", difference)
        self.assertIn("onlyManaged", difference)

    def test_referenced_skills_are_counted_from_the_catalog(self):
        summary = generate_coverage_summary("managed")
        self.assertGreater(summary["skills"]["onDisk"], 0)
        self.assertGreaterEqual(summary["skills"]["referenced"], 0)
        self.assertLessEqual(summary["skills"]["referenced"], summary["skills"]["onDisk"])


class DocumentedCountsTests(unittest.TestCase):
    """The docs must quote the generated numbers, not stale ones."""

    def test_committed_counts_artifact_is_current(self):
        self.assertTrue(
            COUNTS_PATH.is_file(),
            f"{COUNTS_PATH.relative_to(ROOT)} must exist; regenerate it from the registry",
        )
        committed = json.loads(COUNTS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            committed, generate_coverage_summaries(),
            "docs/verification/capability-counts.json is stale; regenerate it",
        )

    def test_readme_quotes_the_managed_totals(self):
        text = README.read_text(encoding="utf-8")
        generated = generate_coverage_summary("managed")
        match = re.search(
            r"(?:records?|registers?)\s+\*{0,2}(\d+)\*{0,2}\s+(?:tools|commands)",
            text, re.IGNORECASE,
        )
        self.assertIsNotNone(
            match,
            "README must state the managed count as 'records/registers N tools|commands'",
        )
        self.assertEqual(
            int(match.group(1)), generated["commands"]["total"],
            "README's tool count must equal the generated managed total",
        )

    def test_readme_states_each_mode_l1_count_in_context(self):
        """A bare substring match would be satisfied by an unrelated number such as '18mm'."""
        text = README.read_text(encoding="utf-8")
        for mode in ("managed", "connector"):
            l1 = generate_coverage_summary(mode)["commands"]["L1"]
            self.assertRegex(
                text, rf"{l1}\s+at\s+L1",
                f"README must state the {mode} L1 count as '{l1} at L1'",
            )

    def test_docs_reference_the_generated_artifact(self):
        for path in (README, README_ZH, COMPLETION_DOC, MATRIX_DOC):
            self.assertTrue(path.is_file(), f"{path} must exist")
            self.assertIn(
                "capability-counts.json", path.read_text(encoding="utf-8"),
                f"{path.relative_to(ROOT)} must reference the generated counts artifact",
            )


class BaselineProvenanceTests(unittest.TestCase):
    """The brief requires source / cache / remote SHA plus the CI commit.

    Undetermined values must be recorded as undetermined (with a reason), never
    omitted and never invented; a recorded SHA must resolve in this repository.
    """

    REQUIRED = (
        ("source", "sha"),
        ("remote", "sha"),
        ("installedCache", "sha"),
        ("ci", "windowsL4", "headSha"),
    )

    def setUp(self):
        self.assertTrue(
            PROVENANCE_PATH.is_file(),
            f"{PROVENANCE_PATH.relative_to(ROOT)} must record the baseline provenance",
        )
        self.data = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))

    def _get(self, path):
        node = self.data
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        return node

    def test_nothing_required_is_silently_omitted(self):
        unresolved = self.data.get("unresolved") or {}
        for path in self.REQUIRED:
            value = self._get(path)
            if not value:
                self.assertIn(
                    ".".join(path), unresolved,
                    f"{'.'.join(path)} is unset, so it must be listed in `unresolved` with a reason",
                )

    def test_recorded_shas_are_real_commits(self):
        """Catches an invented or stale SHA, which a value-only check would miss."""
        for path in (("source", "sha"), ("remote", "sha"), ("ci", "windowsL4", "headSha")):
            sha = self._get(path)
            if not sha:
                continue
            result = subprocess.run(
                ["git", "-C", str(ROOT), "cat-file", "-e", f"{sha}^{{commit}}"],
                capture_output=True,
            )
            self.assertEqual(
                result.returncode, 0,
                f"{'.'.join(path)} {sha} does not resolve to a commit in this repository",
            )

    def test_counts_artifact_is_named(self):
        self.assertIn("capability-counts.json", self.data.get("countsArtifact", ""))

    def test_completion_doc_cites_the_recorded_ci_run(self):
        run_id = str(self._get(("ci", "windowsL4", "runId")))
        self.assertIn(
            run_id, COMPLETION_DOC.read_text(encoding="utf-8"),
            "the completion doc must cite the CI run recorded in the provenance",
        )


if __name__ == "__main__":
    unittest.main()
