"""Import only from caller-approved asset roots."""
from pathlib import Path
from ..errors import HarnessError
from ..identity import ObjectResolver


class AssetCommands:
    def __init__(self, bpy_module, asset_policy=None):
        self.bpy=bpy_module; self.policy=asset_policy; self.objects=ObjectResolver(bpy_module)

    def _path(self, value):
        if self.policy is None: raise HarnessError('ASSET_NOT_AUTHORIZED','no asset root was approved')
        return self.policy.require_file(value)

    def import_file(self, arguments):
        path=self._path(arguments.get('path')); suffix=path.suffix.lower()
        before=set(self.bpy.data.objects)
        try:
            if suffix in {'.glb','.gltf'}: result=self.bpy.ops.import_scene.gltf(filepath=str(path))
            elif suffix=='.fbx': result=self.bpy.ops.wm.fbx_import(filepath=str(path))
            elif suffix=='.obj': result=self.bpy.ops.wm.obj_import(filepath=str(path))
            else: raise HarnessError('INVALID_ARGUMENT','file must be GLB/GLTF, FBX or OBJ')
        except HarnessError: raise
        except Exception as exc: raise HarnessError('IMPORT_FAILED',f'Blender could not import {suffix}') from exc
        if result != {'FINISHED'}: raise HarnessError('IMPORT_FAILED','import operator did not finish')
        created=sorted((obj for obj in self.bpy.data.objects if obj not in before),key=lambda obj:obj.name)
        return {'changedObjects':[obj.name for obj in created], 'result':{'path':str(path),'objects':[self.objects.receipt(obj) for obj in created]}}

    def library(self, arguments):
        path=self._path(arguments.get('path'))
        if path.suffix.lower() != '.blend': raise HarnessError('INVALID_ARGUMENT','library path must be a .blend file')
        kind=str(arguments.get('dataType','OBJECT')).upper(); names=arguments.get('names'); link=arguments.get('link',False)
        if kind not in {'OBJECT','COLLECTION'} or not isinstance(names,list) or not names or any(not isinstance(n,str) or not n for n in names):
            raise HarnessError('INVALID_ARGUMENT','dataType and non-empty names are required')
        if type(link) is not bool: raise HarnessError('INVALID_ARGUMENT','link must be boolean')
        with self.bpy.data.libraries.load(str(path),link=link) as (source,target):
            available=source.objects if kind=='OBJECT' else source.collections
            missing=sorted(set(names)-set(available))
            if missing: raise HarnessError('ASSET_NOT_FOUND',f'library data not found: {missing}')
            if kind=='OBJECT': target.objects=list(names)
            else: target.collections=list(names)
        loaded=target.objects if kind=='OBJECT' else target.collections
        if kind=='OBJECT':
            for obj in loaded:
                if not obj.users_collection: self.bpy.context.scene.collection.objects.link(obj)
            receipts=[self.objects.receipt(obj) for obj in loaded]
        else:
            for collection in loaded:
                if not collection.users_scene: self.bpy.context.scene.collection.children.link(collection)
            receipts=[{'name':collection.name,'type':'COLLECTION'} for collection in loaded]
        return {'changedObjects':[item['name'] for item in receipts], 'result':{'path':str(path),'linked':link,'items':receipts}}

    def pack_resources(self,_arguments):
        result=self.bpy.ops.file.pack_all()
        if result!={'FINISHED'}:raise HarnessError('OPERATION_FAILED','resource packing did not finish')
        packed=sorted(image.name for image in self.bpy.data.images if getattr(image,'packed_file',None))
        return {'changedObjects':[],'result':{'packedImages':packed,'count':len(packed)}}

    def make_paths_relative(self,_arguments):
        result=self.bpy.ops.file.make_paths_relative()
        if result!={'FINISHED'}:raise HarnessError('OPERATION_FAILED','path conversion did not finish')
        return {'changedObjects':[],'result':{'relative':True}}

    FETCH_ALLOWED_HOSTS=frozenset({'api.polyhaven.com','dl.polyhaven.org'})
    FETCH_ALLOWED_SUFFIXES=frozenset({'.hdr','.exr','.glb','.gltf','.png','.jpg','.jpeg'})
    FETCH_MAX_BYTES=200*1024*1024

    def fetch_url(self,arguments):
        """Download an asset from an approved asset-library host into the approved roots."""
        import urllib.request
        from urllib.parse import urlparse
        url=arguments.get('url')
        if not isinstance(url,str) or not url:
            raise HarnessError('INVALID_ARGUMENT','url is required')
        parsed=urlparse(url)
        if parsed.scheme!='https': raise HarnessError('INVALID_ARGUMENT','url must use https')
        if parsed.hostname not in self.FETCH_ALLOWED_HOSTS:
            raise HarnessError('ASSET_NOT_AUTHORIZED',f'asset host is not approved: {parsed.hostname}')
        suffix=Path(parsed.path).suffix.lower()
        if suffix not in self.FETCH_ALLOWED_SUFFIXES:
            raise HarnessError('INVALID_ARGUMENT',f'asset file type is not allowed: {suffix or "(none)"}')
        if self.policy is None: raise HarnessError('ASSET_NOT_AUTHORIZED','no asset root was approved')
        root=self.policy.roots[0]
        subdir=root/'polyhaven'
        filename=arguments.get('filename')
        filename=str(filename) if isinstance(filename,str) and filename.strip() else Path(parsed.path).name
        if '/' in filename or '\\' in filename or '..' in filename: raise HarnessError('INVALID_ARGUMENT','filename must be a plain name')
        if not filename.lower().endswith(suffix): filename+=suffix
        target=subdir/filename
        if target.is_file():
            return {'changedObjects':[],'result':{'path':str(target),'bytes':target.stat().st_size,'cached':True}}
        subdir.mkdir(parents=True,exist_ok=True)
        partial=target.with_name(target.name+'.part')
        downloaded=0
        try:
            with urllib.request.urlopen(url,timeout=120) as response:
                total=response.headers.get('Content-Length')
                if total and int(total)>self.FETCH_MAX_BYTES:
                    raise HarnessError('INVALID_ARGUMENT',f'asset exceeds the {self.FETCH_MAX_BYTES//1024//1024}MB download cap')
                with open(partial,'wb') as sink:
                    while True:
                        chunk=response.read(1024*256)
                        if not chunk: break
                        downloaded+=len(chunk)
                        if downloaded>self.FETCH_MAX_BYTES:
                            raise HarnessError('INVALID_ARGUMENT',f'asset exceeds the {self.FETCH_MAX_BYTES//1024//1024}MB download cap')
                        sink.write(chunk)
        except HarnessError:
            partial.unlink(missing_ok=True)
            raise
        except Exception as exc:
            partial.unlink(missing_ok=True)
            raise HarnessError('DOWNLOAD_FAILED',f'asset download did not finish: {parsed.hostname}') from exc
        partial.replace(target)
        return {'changedObjects':[],'result':{'path':str(target),'bytes':downloaded,'cached':False}}
