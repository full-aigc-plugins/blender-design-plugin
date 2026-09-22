"""供应商兼容状态不能把局部完成或未知状态当成成功。"""
import unittest

from scripts.plugin_mcp_adapter import _generation_state


class GenerationStateTests(unittest.TestCase):
    def test_partial_completion_stays_running(self):
        self.assertEqual(_generation_state({'status_list': ['Done', 'Processing']})[0], 'generating')

    def test_all_results_must_be_completed(self):
        self.assertEqual(_generation_state({'status_list': ['Done', 'Completed']})[:2], ('completed', 1.0))

    def test_unknown_incomplete_string_is_not_success(self):
        self.assertEqual(_generation_state({'status': 'INCOMPLETE'})[0], 'generating')

    def test_failed_result_wins_over_success(self):
        self.assertEqual(_generation_state({'status_list': ['Done', 'Failed']})[0], 'failed')

    def test_cancelled_result_is_terminal(self):
        self.assertEqual(_generation_state({'status': 'CANCELLED'})[0], 'cancelled')

    def test_non_finite_progress_is_not_displayed(self):
        for progress in (float('nan'), float('inf'), float('-inf'), True):
            self.assertIsNone(_generation_state({'status': 'Processing', 'progress': progress})[1])
