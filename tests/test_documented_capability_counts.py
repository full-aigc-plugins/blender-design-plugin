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

    def test_readme_does_not_claim_a_single_merged_l1(self):
        text = README.read_text(encoding="utf-8")
        for mode in ("managed", "connector"):
            generated = generate_coverage_summary(mode)
            self.assertIn(
                str(generated["commands"]["L1"]), text,
                f"README must report the {mode} L1 count ({generated['commands']['L1']})",
            )

    def test_docs_reference_the_generated_artifact(self):
        for path in (README, README_ZH, COMPLETION_DOC, MATRIX_DOC):
            self.assertTrue(path.is_file(), f"{path} must exist")
            self.assertIn(
                "capability-counts.json", path.read_text(encoding="utf-8"),
                f"{path.relative_to(ROOT)} must reference the generated counts artifact",
            )


if __name__ == "__main__":
    unittest.main()
