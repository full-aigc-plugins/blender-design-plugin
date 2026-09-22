"""Regression tests for policies affecting actual dispatch and user takeover."""
import tempfile
import unittest
import uuid
from pathlib import Path

from scripts.harness.execution_policy import ExecutionPolicy
from scripts.harness.runtime import create_session
from scripts.harness.session import HarnessSession
from scripts.harness.transaction import TransactionManager
from tests.test_design_commands import FakeBpy


def call(session, command, arguments=None, tx='work', **extra):
    return session.handle({'protocolVersion':'codex-blender/v1', 'sessionId':session.session_id,
        'requestId':str(uuid.uuid4()), 'transactionId':tx, 'command':command,
        'arguments':arguments or {}, 'expectedSceneRevision':session.scene_revision, **extra})


class PolicyDispatchTests(unittest.TestCase):
    def test_readonly_blocks_mutation_export_transactions_and_expert_even_with_claim(self):
        invoked=[]
        session=HarnessSession('s',dispatch=lambda *a: invoked.append(a) or {},
                               execution_policy=ExecutionPolicy.review_only())
        for command in ['object.create_mesh','export.file','transaction.begin','advanced.execute_python','session.authorize']:
            rid=str(uuid.uuid4())
            response=call(session,command,{'script':'bpy.context.scene.frame_end=9'},
                          requestId=rid,authorization=session.authorization.issue(rid,command))
            self.assertEqual(response['status'],'failed',command)
            self.assertEqual(response['error']['code'],'READ_ONLY_POLICY',command)
        self.assertEqual(invoked,[])
        self.assertEqual(session.scene_revision,0)

    def test_runtime_factory_enforces_selected_policy(self):
        bpy=FakeBpy()
        session=create_session(bpy,'s',execution_policy=ExecutionPolicy.review_only())
        response=call(session,'object.create_mesh',{'name':'Denied','primitive':'cube'})
        self.assertEqual(response['error']['code'],'READ_ONLY_POLICY')
        self.assertNotIn('Denied',bpy.data.objects)

    def test_automatic_export_requires_commit_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bpy=FakeBpy()
            bpy.ops.wm=type('Wm',(),{'save_as_mainfile':lambda _,**kw:Path(kw['filepath']).write_bytes(b'new scene')})()
            policy=ExecutionPolicy.auto_with_budget(str(root),False,None)
            tx=TransactionManager(capture=list,restore=lambda _:None)
            session=create_session(bpy,'s',approved_output_root=root,transactions=tx,execution_policy=policy)
            target=root/'design.blend'
            bad=call(session,'export.file',{'path':str(target),'snapshotId':'none'})
            self.assertEqual(bad['status'],'failed'); self.assertFalse(target.exists())
            call(session,'transaction.begin')
            snap=call(session,'transaction.commit')['snapshotId']
            good=call(session,'export.file',{'path':str(target),'snapshotId':snap})
            self.assertEqual(good['status'],'succeeded',good)
            self.assertEqual(target.read_bytes(),b'new scene')
            for args in [{'path':str(target),'snapshotId':snap},
                         {'path':str(root/'..'/'escape.blend'),'snapshotId':snap},
                         {'path':str(root/'other.blend'),'snapshotId':snap,'overwrite':True}]:
                self.assertEqual(call(session,'export.file',args)['status'],'failed')
            self.assertEqual(target.read_bytes(),b'new scene')

    def test_automatic_does_not_authorize_delete_or_external_uploader(self):
        session=HarnessSession('s',dispatch=lambda *_:{},execution_policy=ExecutionPolicy.auto_with_budget(str(Path.cwd()/'.test-out'),False,None))
        for command in ['object.delete','advanced.execute_python','official_uploader.open_link']:
            response=call(session,command)
            self.assertEqual(response['error']['code'],'AUTHORIZATION_REQUIRED')

    def test_unknown_mode_and_non_boolean_proxy_rule_rejected(self):
        with self.assertRaises(ValueError): ExecutionPolicy('anything')
        with self.assertRaises(ValueError): ExecutionPolicy.auto_with_budget(str(Path.cwd()/'.test-out'),'false',None)

    def test_automatic_format_scope_cannot_be_used_to_export_other_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy=ExecutionPolicy.from_dict({'mode':'auto_with_budget','approvedOutputRoot':tmp,'exportFormats':['blend']})
            self.assertFalse(policy.permits_fresh_export({'path':str(Path(tmp)/'mesh.obj')}))
            self.assertFalse(policy.permits_fresh_export({'path':str(Path(tmp)/'file.blend'),'overwrite':1}))
            self.assertTrue(policy.permits_fresh_export({'path':str(Path(tmp)/'file.blend')}))

    def test_preview_path_escape_is_rejected_before_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=create_session(FakeBpy(),'s',approved_output_root=Path(tmp),execution_policy=ExecutionPolicy.review_only())
            result=call(session,'preview.capture',{'snapshotId':'../../outside'})
            self.assertEqual(result['error']['code'],'INVALID_ARGUMENT')


class TakeoverTests(unittest.TestCase):
    def test_native_takeover_is_audited_without_a_remote_request(self):
        session=HarnessSession('s',dispatch=lambda *_:{})
        session.pause()
        session.resume_local()
        self.assertEqual([entry['command'] for entry in session.audit_entries()],['session.pause','session.resume'])
        self.assertTrue(all(entry['source']=='local_ui' for entry in session.audit_entries()))

    def test_pause_blocks_mutation_and_requires_fresh_inspection_after_resume(self):
        invoked=[]
        session=HarnessSession('s',dispatch=lambda *a:invoked.append(a) or {})
        self.assertEqual(call(session,'session.pause')['status'],'succeeded')
        response=call(session,'object.create_mesh')
        self.assertEqual(response['error']['code'],'SESSION_PAUSED')
        self.assertEqual(invoked,[])
        rid='resume'
        claim=session.authorization.issue(rid,'session.resume')
        self.assertEqual(call(session,'session.resume',requestId=rid,authorization=claim)['status'],'succeeded')
        self.assertEqual(call(session,'object.create_mesh')['error']['code'],'REINSPECTION_REQUIRED')
        call(session,'scene.inspect')
        self.assertEqual(call(session,'object.create_mesh')['status'],'succeeded')

    def test_takeover_prevents_rollback_of_user_changes(self):
        values=[]
        manager=TransactionManager(capture=lambda:list(values),restore=lambda x:values.__setitem__(slice(None),x))
        session=HarnessSession('s',dispatch=lambda *_:{},transactions=manager)
        call(session,'transaction.begin')
        call(session,'session.pause')
        values.append('user edit')
        rid='resume'; claim=session.authorization.issue(rid,'session.resume')
        call(session,'session.resume',requestId=rid,authorization=claim)
        call(session,'scene.inspect')
        response=call(session,'transaction.rollback')
        self.assertEqual(response['status'],'failed')
        self.assertEqual(values,['user edit'])

    def test_progress_and_changed_objects_visible_in_status(self):
        session=HarnessSession('s',dispatch=lambda *_:{'changedObjects':['Hero']})
        response=call(session,'session.set_progress',{'stage':'Blocking','progress':.25})
        self.assertEqual(response['status'],'succeeded')
        call(session,'object.transform',{'name':'Hero'})
        result=call(session,'session.status')['result']
        self.assertEqual(result['stage'],'Blocking')
        self.assertEqual(result['progress'],.25)
        self.assertEqual(result['changedObjects'],['Hero'])
        self.assertEqual(result['lastCommand'],'object.transform')

    def test_revoked_session_rejects_previously_unseen_commands(self):
        session=HarnessSession('s',dispatch=lambda *_:{})
        session.revoke()
        self.assertEqual(call(session,'object.create_mesh')['error']['code'],'SESSION_REVOKED')

    def test_progress_rejects_nan_and_unknown_fields(self):
        session=HarnessSession('s',dispatch=lambda *_:{})
        for args in [{'stage':'test','progress':float('nan')},{'stage':'test','extra':'bad'}]:
            self.assertEqual(call(session,'session.set_progress',args)['error']['code'],'INVALID_ARGUMENT')

    def test_resume_requires_explicit_authorization(self):
        session=HarnessSession('s',dispatch=lambda *_:{})
        call(session,'session.pause')
        self.assertEqual(call(session,'session.resume')['error']['code'],'AUTHORIZATION_REQUIRED')
        self.assertTrue(session.paused)


if __name__=='__main__': unittest.main()
