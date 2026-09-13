import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from scripts.harness.frame_worker import compose_video, render_frame_sequence


def _png(width,height,color_type=6,payload=b''):
    return b'\x89PNG\r\n\x1a\n'+struct.pack('>I',13)+b'IHDR'+struct.pack('>II',width,height)+bytes((16,color_type,0,0,0))+payload


class _Scene:
    def __init__(self):
        self.frame_current=1;self.frame_start=1;self.frame_end=3
        self.render=type('Render',(),{})();self.render.filepath='original';self.render.resolution_x=640
        self.render.resolution_y=480;self.render.resolution_percentage=50;self.render.fps=24;self.render.fps_base=2.0
        self.render.image_settings=type('Image',(),{'media_type':'IMAGE','file_format':'PNG','color_mode':'RGB','color_depth':'8'})()
        self.sequence_editor=None
    def frame_set(self,frame):self.frame_current=frame


class _Bpy:
    def __init__(self):
        self.context=type('Context',(),{'scene':_Scene()})();self.rendered=[]
        render=type('RenderOps',(),{})();render.render=self._render
        self.ops=type('Ops',(),{'render':render})()
    def _render(self,write_still=False):
        frame=self.context.scene.frame_current;self.rendered.append(frame)
        render=self.context.scene.render;color_type=6 if render.image_settings.color_mode=='RGBA' else 2
        content=(b'\x76\x2f\x31\x01'+f'render-{frame}'.encode() if render.image_settings.media_type=='MULTI_LAYER_IMAGE'
                 else _png(render.resolution_x,render.resolution_y,color_type,f'render-{frame}'.encode()))
        Path(render.filepath).write_bytes(content)


class FrameWorkerTests(unittest.TestCase):
    def test_render_reuses_verified_frames_and_replaces_only_bad_or_missing_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            task=Path(directory);frames=task/'frames';frames.mkdir();good=frames/'frame_000001.png';good.write_bytes(_png(1280,720,6,b'approved'));approved=good.read_bytes()
            manifest={'receiptVersion':'3.0.0','frameStart':1,'frameEnd':3,'frameStep':1,'format':'PNG','fps':24,'frames':[
              {'frame':1,'path':str(good),'bytes':good.stat().st_size,'sha256':hashlib.sha256(good.read_bytes()).hexdigest()}]}
            (task/'frame-sequence.json').write_text(json.dumps(manifest))
            bpy=_Bpy();statuses=[];spec={'jobId':'job_frames','kind':'RENDER_ANIMATION_FRAMES','snapshot':{'sha256':'snapshot'},'parameters':{
              'frameStart':1,'frameEnd':3,'frameStep':1,'frames':[1,2,3],'width':1280,'height':720,'imageFormat':'PNG',
              'extension':'png','colorMode':'RGBA','colorDepth':'16','includeAudio':False}}
            receipt=render_frame_sequence(bpy,task,spec,statuses.append)
            self.assertEqual(bpy.rendered,[2,3]);self.assertEqual(receipt['reusedFrames'],[1]);self.assertEqual(receipt['renderedFrames'],[2,3])
            self.assertEqual(good.read_bytes(),approved);self.assertEqual(receipt['validation']['status'],'passed')
            self.assertEqual(receipt['fps'],12.0)
            self.assertEqual(bpy.context.scene.render.filepath,'original')

    def test_compose_binds_manifest_hash_and_returns_verified_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'job_frames';frames=source/'frames';frames.mkdir(parents=True);entries=[]
            for frame in (1,2):
                path=frames/f'frame_{frame:06d}.png';path.write_bytes(b'frame')
                entries.append({'frame':frame,'path':str(path),'bytes':5,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            manifest_path=source/'frame-sequence.json';manifest_path.write_text(json.dumps({'receiptVersion':'3.0.0','frameStart':1,'frameEnd':2,
              'frameStep':1,'format':'PNG','fps':24,'frames':entries}))
            task=root/'job_compose';task.mkdir();spec={'jobId':'job_compose','kind':'COMPOSE_VIDEO','snapshot':{'sha256':'snapshot'},
              'parameters':{'sourceJobId':'job_frames','codec':'H264','crf':20,'preset':'medium','pixelFormat':'yuv420p','includeAudio':False},
              'sourceSequence':{'jobId':'job_frames','manifestPath':str(manifest_path),
                'manifestSha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest()}}
            def runner(command,**kwargs):
                Path(command[-1]).write_bytes(b'mp4')
                return type('Process',(),{'returncode':0,'stderr':''})()
            fake_ffmpeg=root/'ffmpeg';fake_ffmpeg.write_bytes(b'executable')
            receipt=compose_video(task,spec,runner=runner,ffmpeg_path=fake_ffmpeg,
              video_probe=lambda path:{'codec':'h264','width':1280,'height':720,'fps':24.0,'duration_seconds':0.08})
            self.assertEqual(receipt['format'],'mp4');self.assertEqual(receipt['validation']['status'],'passed')
            self.assertTrue(Path(receipt['path']).is_file())

    def test_compose_rejects_a_manifest_outside_the_declared_source_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);outside=root/'outside';outside.mkdir();manifest=outside/'frame-sequence.json'
            manifest.write_text(json.dumps({'frameStart':1,'frameEnd':1,'frameStep':1,'frames':[]}))
            task=root/'job_compose';task.mkdir();spec={'jobId':'job_compose','kind':'COMPOSE_VIDEO','snapshot':{'sha256':'snapshot'},
              'parameters':{'sourceJobId':'job_frames','codec':'H264','crf':20,'preset':'medium','pixelFormat':'yuv420p','includeAudio':False},
              'sourceSequence':{'jobId':'job_frames','manifestPath':str(manifest),
                'manifestSha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}}
            from scripts.harness.errors import HarnessError
            with self.assertRaises(HarnessError) as caught:
                compose_video(task,spec,ffmpeg_path=root/'ffmpeg')
            self.assertEqual(caught.exception.code,'SOURCE_NOT_AUTHORIZED')

    def test_multilayer_exr_selects_blender_52_media_type_and_restores_it(self):
        with tempfile.TemporaryDirectory() as directory:
            task=Path(directory);bpy=_Bpy();spec={'jobId':'job_exr','kind':'RENDER_ANIMATION_FRAMES','snapshot':{'sha256':'snapshot'},
              'parameters':{'frameStart':1,'frameEnd':1,'frameStep':1,'frames':[1],'width':1280,'height':720,
              'imageFormat':'OPEN_EXR_MULTILAYER','extension':'exr','colorMode':'RGBA','colorDepth':'16','includeAudio':False}}
            receipt=render_frame_sequence(bpy,task,spec)
            self.assertEqual(receipt['format'],'OPEN_EXR_MULTILAYER');self.assertEqual(bpy.context.scene.render.image_settings.media_type,'IMAGE')


if __name__=='__main__':unittest.main()
