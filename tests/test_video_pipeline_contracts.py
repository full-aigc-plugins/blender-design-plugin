import unittest

from scripts.validate_document import validate_document


HASH='a'*64


class VideoPipelineContractTests(unittest.TestCase):
    def test_render_plan_is_closed(self):
        plan={'schemaVersion':'1.0.0','jobId':'job_frames','frameStart':1,'frameEnd':24,'frameStep':1,
              'width':1280,'height':720,'imageFormat':'PNG','colorMode':'RGBA','colorDepth':'16','includeAudio':True}
        self.assertEqual(validate_document('render_plan',plan),[])
        self.assertTrue(validate_document('render_plan',{**plan,'unknown':1}))

    def test_frame_sequence_receipt_matches_worker_output(self):
        receipt={'receiptVersion':'3.0.0','protocolVersion':'codex-blender/v1','producer':{'name':'codex-blender','version':'0.3.0'},
          'jobId':'job_frames','snapshotSha256':HASH,'frameStart':1,'frameEnd':1,'frameStep':1,'format':'PNG',
          'width':1280,'height':720,'colorMode':'RGBA','colorDepth':'16','frames':[{'frame':1,'path':'/approved/frame.png',
          'bytes':10,'sha256':HASH}],'fps':24.0,'reusedFrames':[],'renderedFrames':[1],
          'validation':{'status':'passed','checks':['sha256']}}
        self.assertEqual(validate_document('frame_sequence_receipt',receipt),[])

    def test_video_artifact_receipt_matches_compose_output(self):
        receipt={'receiptVersion':'3.0.0','protocolVersion':'codex-blender/v1','producer':{'name':'codex-blender','version':'0.3.0'},
          'jobId':'job_video','path':'/approved/video.mp4','format':'mp4','bytes':100,'sha256':HASH,
          'sourceSequence':{'jobId':'job_frames','manifestPath':'/approved/frame-sequence.json','manifestSha256':HASH},
          'media':{'codec':'h264','width':1280,'height':720,'fps':24.0,'duration_seconds':1.0},
          'validation':{'status':'passed','checks':['ffprobe']}}
        self.assertEqual(validate_document('video_artifact_receipt',receipt),[])


if __name__=='__main__':unittest.main()
