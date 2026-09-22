"""Public viewport controls and queue cancellation, without requiring Blender in CI."""
import threading
import time
import unittest

from scripts.harness.execution_policy import ExecutionPolicy
from scripts.harness.main_thread import MainThreadExecutor
from scripts.harness.runtime import create_session
from tests.test_design_commands import FakeBpy
from tests.test_foreground_policy import call


class ViewControlTests(unittest.TestCase):
    def test_present_without_a_viewport_does_not_claim_success(self):
        session=create_session(FakeBpy(),'s')
        result=call(session,'view.present')
        self.assertEqual(result['error']['code'],'FRONTEND_UNAVAILABLE')

    def test_set_frame_is_readonly_and_validates_frame_range(self):
        bpy=FakeBpy()
        bpy.context.scene.frame_set=lambda n:setattr(bpy.context.scene,'frame_current',n)
        session=create_session(bpy,'s',execution_policy=ExecutionPolicy.review_only())
        response=call(session,'playback.set_frame',{'frame':50})
        self.assertEqual(response['status'],'succeeded',response)
        self.assertEqual(bpy.context.scene.frame_current,50)
        self.assertEqual(session.scene_revision,0)
        for n in (True,0,251):
            self.assertEqual(call(session,'playback.set_frame',{'frame':n})['status'],'failed')
        self.assertEqual(bpy.context.scene.frame_current,50)

    def test_view_commands_are_closed_and_headless_does_not_claim_a_window(self):
        session=create_session(FakeBpy(),'s')
        bad=call(session,'view.set',{'view':'CAMERA','script':'arbitrary'})
        self.assertEqual(bad['error']['code'],'INVALID_ARGUMENT')
        missing=call(session,'view.set',{'view':'CAMERA'})
        self.assertEqual(missing['error']['code'],'FRONTEND_UNAVAILABLE')


class QueueCancellationTests(unittest.TestCase):
    def test_cancel_pending_work_prevents_callback_execution(self):
        executor=MainThreadExecutor(); calls=[]; errors=[]
        def submit():
            try: executor.submit(lambda:calls.append('executed'),timeout=2)
            except Exception as exc: errors.append(exc)
        threads=[threading.Thread(target=submit) for _ in range(2)]
        for thread in threads: thread.start()
        deadline=time.monotonic()+1
        while executor.pending_count<2 and time.monotonic()<deadline: time.sleep(.001)
        executor.cancel_pending('SESSION_PAUSED')
        for thread in threads: thread.join(2)
        executor.pump()
        self.assertEqual(calls,[])
        self.assertEqual([e.code for e in errors],['SESSION_PAUSED','SESSION_PAUSED'])


if __name__=='__main__': unittest.main()
