import unittest

from scripts.harness.execution_policy import ExecutionMode, ExecutionPolicy, ExecutionPolicyError


class TestExecutionPolicy(unittest.TestCase):
    def test_auto_policy_suppresses_milestone_review_but_not_irreversible_actions(self):
        policy = ExecutionPolicy.auto_with_budget(
            approved_output_root="/tmp/codex-out",
            allow_designed_proxies=True,
            downstream_budget_limit="3.20",
        )
        self.assertEqual(policy.mode, ExecutionMode.AUTO_WITH_BUDGET)
        self.assertFalse(policy.requires_user_review("milestone_complete"))
        self.assertFalse(policy.requires_user_review("final_artifact_report"))
        self.assertTrue(policy.requires_user_review("overwrite"))
        self.assertTrue(policy.requires_user_review("delete"))
        self.assertTrue(policy.requires_user_review("budget_exceeded"))

    def test_auto_policy_requires_output_root_and_non_negative_budget(self):
        with self.assertRaises(ExecutionPolicyError):
            ExecutionPolicy.auto_with_budget(None, False, None)
        with self.assertRaises(ExecutionPolicyError):
            ExecutionPolicy.auto_with_budget("/tmp/out", False, "-0.01")

    def test_review_only_never_permits_mutation_or_export(self):
        policy = ExecutionPolicy.review_only()
        self.assertTrue(policy.requires_user_review("mutation"))
        self.assertTrue(policy.requires_user_review("export"))
        self.assertTrue(policy.requires_user_review("milestone_complete"))

