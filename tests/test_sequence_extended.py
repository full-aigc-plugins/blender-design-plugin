import tempfile
import unittest
from pathlib import Path

from scripts.harness.commands.sequence import SequenceCommands
from scripts.harness.path_policy import PathPolicy


class _Elements(list):
    def append(self,value):super().append(type('Element',(),{'filename':value})());return self[-1]


class _Strip:
    def __init__(self,name,kind,channel,start,duration=10):
        self.name=name;self.type=kind;self.channel=channel;self.frame_start=start;self.frame_final_start=start
        self.frame_final_duration=duration;self.frame_final_end=start+duration;self.elements=_Elements();self.volume=1.0;self.keyframes=[]
    def keyframe_insert(self,**kwargs):self.keyframes.append(kwargs)


class _Strips:
    def __init__(self):self.items={};self.bl_rna=type('Rna',(),{'functions':{'new_effect':type('Fn',(),{'parameters':[type('P',(),{'identifier':'length'})()]})()}})()
    def get(self,name):return self.items.get(name)
    def __iter__(self):return iter(self.items.values())
    def remove(self,strip):self.items.pop(strip.name,None)
    def _put(self,strip):self.items[strip.name]=strip;return strip
    def new_image(self,name,path,channel,start):return self._put(_Strip(name,'IMAGE',channel,start,1))
    def new_scene(self,name,scene,channel,start):return self._put(_Strip(name,'SCENE',channel,start,scene.frame_end-scene.frame_start+1))
    def new_effect(self,**kwargs):
        strip=_Strip(kwargs['name'],kwargs['type'],kwargs['channel'],kwargs['frame_start'],kwargs['length']);strip.input_1=kwargs.get('input1');return self._put(strip)


class _Bpy:
    def __init__(self):
        self.editor=type('Editor',(),{'strips':_Strips()})();scene=type('Scene',(),{'frame_start':1,'frame_end':24})()
        active=type('ActiveScene',(),{'sequence_editor':self.editor,'sequence_editor_create':lambda _:self.editor})()
        self.context=type('Context',(),{'scene':active})();self.data=type('Data',(),{'scenes':{'Shot':scene}})()


class ExtendedSequenceTests(unittest.TestCase):
    def test_scene_image_sequence_and_text_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);paths=[]
            for index in range(3):
                path=root/f'{index}.png';path.write_bytes(b'image');paths.append(str(path))
            commands=SequenceCommands(_Bpy(),PathPolicy((root,)))
            scene=commands.add({'type':'SCENE','name':'Scene','scene':'Shot','channel':1,'frameStart':1})['result']
            images=commands.add({'type':'IMAGE_SEQUENCE','name':'Frames','paths':paths,'channel':2,'frameStart':1})['result']
            text=commands.add({'type':'TEXT','name':'Caption','text':'Hello','duration':12,'channel':3,'frameStart':1})['result']
            self.assertEqual(scene['type'],'SCENE');self.assertEqual(images['elements'],3);self.assertEqual(text['text'],'Hello')

    def test_transition_speed_and_volume_animation_use_closed_parameters(self):
        bpy=_Bpy();commands=SequenceCommands(bpy)
        first=bpy.editor.strips._put(_Strip('A','IMAGE',1,1,20));second=bpy.editor.strips._put(_Strip('B','IMAGE',2,11,20))
        transition=commands.transition({'name':'Wipe','first':'A','second':'B','channel':3,'transitionType':'WIPE'})['result']
        speed=commands.set_speed({'name':'Fast','source':'A','channel':4,'factor':1.5})['result']
        volume_strip=bpy.editor.strips._put(_Strip('Voice','SOUND',5,1,20))
        volume=commands.keyframe_volume({'name':'Voice','frame':10,'volume':0.25})['result']
        sound_a=bpy.editor.strips._put(_Strip('SoundA','SOUND',6,1,20));sound_b=bpy.editor.strips._put(_Strip('SoundB','SOUND',7,11,20))
        crossfade=commands.transition({'name':'AudioFade','first':'SoundA','second':'SoundB','channel':8,
                                       'transitionType':'SOUND_CROSSFADE'})['result']
        self.assertEqual(transition['type'],'WIPE');self.assertEqual(speed['factor'],1.5)
        self.assertEqual(volume_strip.keyframes[0],{'data_path':'volume','frame':10});self.assertEqual(volume['volume'],.25)
        self.assertFalse(crossfade['createsStrip']);self.assertEqual(len(sound_a.keyframes),2);self.assertEqual(len(sound_b.keyframes),2)


if __name__=='__main__':unittest.main()
