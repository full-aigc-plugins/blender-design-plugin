import hashlib,json,tempfile,unittest
from pathlib import Path
from scripts.harness.jobs import JobManager
from scripts.harness.errors import HarnessError
from tests.test_design_commands import FakeBpy


class BackgroundJobRecoveryTests(unittest.TestCase):
    class _Process:
        pid=4242
        returncode=None
        def poll(self):return None
        def terminate(self):self.returncode=-15
        def wait(self,timeout=None):return self.returncode

    class _JobBpy:
        def __init__(self):
            self.app=type('App',(),{'binary_path':'/Applications/Blender.app/Contents/MacOS/Blender'})()
            self.data=type('Data',(),{'filepath':''})()
            wm=type('Wm',(),{})();wm.save_as_mainfile=self._save
            self.ops=type('Ops',(),{'wm':wm})()
        @staticmethod
        def _save(**kwargs):
            Path(kwargs['filepath']).write_bytes(b'blend')
            return {'FINISHED'}

    def test_missing_worker_is_marked_interrupted_without_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=JobManager(FakeBpy(),Path(directory)); task=Path(directory)/'jobs'/'job_lost'; task.mkdir()
            (task/'status.json').write_text(json.dumps({'receiptVersion':'2.0.0','jobId':'job_lost','kind':'EXPORT','state':'running','pid':99999999}))
            result=manager.recover({'jobId':'job_lost'})['result']
            self.assertEqual(result['state'],'interrupted'); self.assertEqual(result['recovery'],'not-restarted')
            self.assertEqual(manager.recover({'jobId':'job_lost'})['result']['state'],'interrupted')

    def test_invalid_job_id_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(HarnessError):JobManager(FakeBpy(),Path(directory)).status({'jobId':'../outside'})

    def test_render_job_limits_are_checked_before_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=JobManager(FakeBpy(),Path(directory))
            for parameters in ({'width':20000},{'height':0},{'unexpected':1}):
                with self.subTest(parameters=parameters),self.assertRaises(HarnessError):
                    manager.submit({'kind':'RENDER_STILL','parameters':parameters})
            self.assertEqual(list((Path(directory)/'jobs').iterdir()),[])

    def test_animation_and_compose_job_parameters_fail_closed_before_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=JobManager(FakeBpy(),Path(directory))
            invalid=(
                {'kind':'RENDER_ANIMATION_FRAMES','parameters':{'frameStart':1,'frameEnd':2,'imageFormat':'JPEG'}},
                {'kind':'RENDER_ANIMATION_FRAMES','parameters':{'frameStart':2,'frameEnd':1}},
                {'kind':'COMPOSE_VIDEO','parameters':{'sourceJobId':'../escape'}},
            )
            for request in invalid:
                with self.subTest(request=request),self.assertRaises(HarnessError):manager.submit(request)
            self.assertEqual(list((Path(directory)/'jobs').iterdir()),[])

    def test_animation_job_persists_normalized_render_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=JobManager(self._JobBpy(),Path(directory),process_factory=lambda *args,**kwargs:self._Process())
            result=manager.submit({'kind':'RENDER_ANIMATION_FRAMES','jobId':'job_frames','parameters':{
                'frameStart':1,'frameEnd':3,'width':1280,'height':720,'includeAudio':False}})['result']
            spec=json.loads((Path(directory)/'jobs'/'job_frames'/'spec.json').read_text())
            self.assertEqual(result['receiptVersion'],'3.0.0')
            self.assertEqual(spec['parameters']['frames'],[1,2,3])
            self.assertEqual(spec['parameters']['imageFormat'],'PNG')

    def test_compose_job_requires_a_complete_verified_source_sequence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manager=JobManager(self._JobBpy(),root,process_factory=lambda *args,**kwargs:self._Process());source=root/'jobs'/'job_frames';frames=source/'frames';frames.mkdir(parents=True)
            entries=[]
            for frame in (1,2):
                path=frames/f'frame_{frame:06d}.png';path.write_bytes(f'frame-{frame}'.encode())
                entries.append({'frame':frame,'path':str(path),'bytes':path.stat().st_size,
                                'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            (source/'frame-sequence.json').write_text(json.dumps({'receiptVersion':'3.0.0','frameStart':1,'frameEnd':2,
              'frameStep':1,'fps':24,'format':'PNG','frames':entries}))
            result=manager.submit({'kind':'COMPOSE_VIDEO','jobId':'job_compose','parameters':{'sourceJobId':'job_frames'}})['result']
            spec=json.loads((root/'jobs'/'job_compose'/'spec.json').read_text())
            self.assertEqual(result['kind'],'COMPOSE_VIDEO');self.assertEqual(spec['sourceSequence']['jobId'],'job_frames')
            (frames/'frame_000002.png').write_bytes(b'corrupt')
            with self.assertRaises(HarnessError):
                manager.submit({'kind':'COMPOSE_VIDEO','jobId':'job_bad','parameters':{'sourceJobId':'job_frames'}})

    def test_resume_restarts_only_an_interrupted_frame_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manager=JobManager(self._JobBpy(),root,process_factory=lambda *args,**kwargs:self._Process());task=root/'jobs'/'job_frames';task.mkdir(parents=True)
            snapshot=task/'source.blend';snapshot.write_bytes(b'blend')
            spec={'jobId':'job_frames','kind':'RENDER_ANIMATION_FRAMES','format':'','parameters':{
              'frameStart':1,'frameEnd':2,'frameStep':1,'frames':[1,2],'width':1280,'height':720,
              'imageFormat':'PNG','extension':'png','colorMode':'RGBA','colorDepth':'16','includeAudio':False},
              'snapshot':{'path':str(snapshot),'sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest(),'sceneFile':''}}
            (task/'spec.json').write_text(json.dumps(spec));(task/'status.json').write_text(json.dumps({
              'receiptVersion':'3.0.0','jobId':'job_frames','kind':'RENDER_ANIMATION_FRAMES','state':'interrupted','attempt':1,
              'snapshot':spec['snapshot']}))
            resumed=manager.resume({'jobId':'job_frames'})['result']
            self.assertEqual(resumed['state'],'running');self.assertEqual(resumed['attempt'],2)

    def test_status_rereads_terminal_receipt_after_worker_exit_race(self):
        """Do not overwrite a receipt written between the first read and poll()."""
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);task=root/'jobs'/'job_frames';task.mkdir(parents=True)
            status_path=task/'status.json'
            running={'receiptVersion':'3.0.0','jobId':'job_frames','kind':'RENDER_ANIMATION_FRAMES',
                     'state':'running','attempt':2}
            completed=running|{'state':'completed','artifact':{'path':'frames'}}
            status_path.write_text(json.dumps(running))

            class ExitAfterReceipt:
                returncode=0
                def poll(self):
                    status_path.write_text(json.dumps(completed))
                    return 0

            manager=JobManager(self._JobBpy(),root)
            manager.processes['job_frames']=ExitAfterReceipt()
            result=manager.status({'jobId':'job_frames'})['result']
            self.assertEqual(result,completed)
            self.assertEqual(json.loads(status_path.read_text()),completed)
