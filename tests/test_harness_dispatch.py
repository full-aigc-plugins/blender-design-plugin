import threading
import time
import unittest

from scripts.harness.errors import HarnessError
from scripts.harness.main_thread import MainThreadExecutor
from scripts.harness.registry import CommandRegistry


class TestCommandRegistry(unittest.TestCase):
    def test_unknown_command_fails_closed(self):
        registry = CommandRegistry()
        with self.assertRaises(HarnessError) as caught:
            registry.dispatch("unknown.command", {})
        self.assertEqual(caught.exception.code, "UNKNOWN_COMMAND")

    def test_validator_runs_before_handler(self):
        called = []
        registry = CommandRegistry()
        registry.register(
            "object.rename",
            lambda args: called.append(args) or {},
            validate=lambda args: (_ for _ in ()).throw(HarnessError("INVALID_ARGUMENT", "bad")),
        )
        with self.assertRaises(HarnessError):
            registry.dispatch("object.rename", {"name": "x"})
        self.assertEqual(called, [])

    def test_duplicate_registration_is_rejected(self):
        registry = CommandRegistry()
        registry.register("scene.inspect", lambda _args: {})
        with self.assertRaises(HarnessError) as caught:
            registry.register("scene.inspect", lambda _args: {})
        self.assertEqual(caught.exception.code, "DUPLICATE_COMMAND")


class TestMainThreadExecutor(unittest.TestCase):
    def test_worker_submission_executes_only_when_main_thread_pumps(self):
        executor = MainThreadExecutor(owner_thread_id=threading.get_ident())
        executed_on = []
        result = []

        def worker():
            result.append(executor.submit(lambda: executed_on.append(threading.get_ident()) or 42, timeout=2))

        thread = threading.Thread(target=worker)
        thread.start()
        time.sleep(0.02)
        self.assertEqual(executed_on, [])
        self.assertEqual(executor.pump(), 1)
        thread.join(timeout=2)
        self.assertEqual(result, [42])
        self.assertEqual(executed_on, [threading.get_ident()])

    def test_pump_from_wrong_thread_is_rejected(self):
        executor = MainThreadExecutor(owner_thread_id=-1)
        with self.assertRaises(HarnessError) as caught:
            executor.pump()
        self.assertEqual(caught.exception.code, "MAIN_THREAD_REQUIRED")

    def test_command_exception_propagates_to_submitter(self):
        executor = MainThreadExecutor(owner_thread_id=threading.get_ident())
        errors = []

        def worker():
            try:
                executor.submit(lambda: (_ for _ in ()).throw(ValueError("boom")), timeout=2)
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=worker)
        thread.start()
        time.sleep(0.02)
        executor.pump()
        thread.join(timeout=2)
        self.assertIsInstance(errors[0], ValueError)


if __name__ == "__main__":
    unittest.main()
