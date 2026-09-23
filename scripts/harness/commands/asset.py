"""Import only from caller-approved asset roots."""
from pathlib import Path

from ..errors import HarnessError
from ..identity import ObjectResolver
from ..dependencies import generate_manifest, package_project, validate_portability


class AssetCommands:
    def __init__(self, bpy_module, asset_policy=None, output_root=None):
        self.bpy=bpy_module; self.policy=asset_policy; self.objects=ObjectResolver(bpy_module)
        self.output_root=output_root

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
    POLYPIZZA_API_BASE='https://api.poly.pizza/v1.1'
    POLYPIZZA_MAX_BYTES=100*1024*1024
    POLYPIZZA_SUFFIXES=frozenset({'.glb','.gltf'})

    def _polypizza_headers(self):
        import os
        key=os.environ.get('POLYPIZZA_API_KEY')
        if not key:
            raise HarnessError('POLYPIZZA_KEY_MISSING','set POLYPIZZA_API_KEY (free key: https://poly.pizza/settings/api)')
        return {'x-auth-token':key,'User-Agent':'partme-blender-plugin'}

    def _polypizza_fetch_json(self, path):
        import urllib.request
        request=urllib.request.Request(self.POLYPIZZA_API_BASE+path,headers=self._polypizza_headers())
        try:
            with urllib.request.urlopen(request,timeout=30) as response:
                import json as _json
                return _json.loads(response.read().decode('utf-8'))
        except HarnessError: raise
        except Exception as exc: raise HarnessError('DOWNLOAD_FAILED','Poly Pizza API request did not finish') from exc

    def polypizza_search(self,arguments):
        """Search the Poly Pizza low-poly library (API key via POLYPIZZA_API_KEY env)."""
        from urllib.parse import quote
        query=arguments.get('query')
        licence=arguments.get('licence')
        if licence not in (None,'','CC0','CC-BY'):
            raise HarnessError('INVALID_ARGUMENT',"licence must be 'CC0' or 'CC-BY'")
        limit=arguments.get('limit',8)
        if not isinstance(limit,int) or not 1<=limit<=32: raise HarnessError('INVALID_ARGUMENT','limit must be an integer in 1-32')
        params=[f'Limit={limit}']
        if isinstance(licence,str) and licence:
            params.append('License=1' if licence=='CC0' else 'License=0')
        path='/search/'+quote(str(query),safe='') if query else '/search'
        data=self._polypizza_fetch_json(path+'?'+'&'.join(params))
        models=[]
        for item in data.get('results',[]) if isinstance(data,dict) else []:
            creator=item.get('Creator') or {}
            models.append({'id':item.get('ID'),'title':item.get('Title'),
                           'creator':creator.get('Username') if isinstance(creator,dict) else None,
                           'licence':'CC-BY' if item.get('Licence')==0 else 'CC0',
                           'triCount':item.get('Tri Count'),'animated':bool(item.get('Animated'))})
        return {'changedObjects':[],'result':{'total':data.get('total',len(models)) if isinstance(data,dict) else 0,'models':models}}

    def polypizza_download(self,arguments):
        """Download a Poly Pizza model into the approved roots and record its CC-BY attribution."""
        import json as _json
        import urllib.request
        from urllib.parse import quote, urlparse
        model_id=arguments.get('modelId')
        if not isinstance(model_id,str) or not model_id.strip():
            raise HarnessError('INVALID_ARGUMENT','modelId is required')
        detail=self._polypizza_fetch_json('/model/'+quote(model_id.strip(),safe=''))
        if not isinstance(detail,dict) or not detail.get('Download'):
            raise HarnessError('ASSET_NOT_FOUND',f'no downloadable file for model: {model_id}')
        download_url=str(detail['Download'])
        parsed=urlparse(download_url)
        suffix=Path(parsed.path).suffix.lower()
        if suffix not in self.POLYPIZZA_SUFFIXES:
            suffix='.glb' if 'glb' in download_url.lower() else '.zip'
        if self.policy is None: raise HarnessError('ASSET_NOT_AUTHORIZED','no asset root was approved')
        root=self.policy.roots[0]
        subdir=root/'polypizza'/model_id.strip()
        subdir.mkdir(parents=True,exist_ok=True)
        target=subdir/('model'+suffix)
        creator=(detail.get('Creator') or {})
        creator_name=creator.get('Username') if isinstance(creator,dict) else None
        licence='CC0' if detail.get('Licence')==1 else 'CC-BY'
        attribution=f"Model '{detail.get('Title', model_id)}' by {creator_name or 'unknown'} — {licence} — https://poly.pizza/m/{model_id}"
        downloaded=0
        partial=target.with_name(target.name+'.part')
        try:
            with urllib.request.urlopen(download_url,timeout=180) as response:  # noqa: SIM117
                with open(partial,'wb') as sink:
                    while True:
                        chunk=response.read(1024*256)
                        if not chunk: break
                        downloaded+=len(chunk)
                        if downloaded>self.POLYPIZZA_MAX_BYTES:
                            raise HarnessError('INVALID_ARGUMENT',f'model exceeds the {self.POLYPIZZA_MAX_BYTES//1024//1024}MB download cap')
                        sink.write(chunk)
        except HarnessError:
            partial.unlink(missing_ok=True); raise
        except Exception as exc:
            partial.unlink(missing_ok=True)
            raise HarnessError('DOWNLOAD_FAILED','Poly Pizza model download did not finish (CDN may block datacenter IPs; retry from a regular connection or download manually at https://poly.pizza)') from exc
        partial.replace(target)
        sidecar=subdir/'license.json'
        sidecar.write_text(_json.dumps({'attribution':attribution,'title':detail.get('Title'),'creator':creator_name,'licence':licence,'source':f'https://poly.pizza/m/{model_id}'},ensure_ascii=False,indent=1),encoding='utf-8')
        return {'changedObjects':[],'result':{'path':str(target),'bytes':downloaded,'licence':licence,'attribution':attribution,'sidecar':str(sidecar)}}

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

    def dependencies(self, arguments):
        """List all external file dependencies in the current project."""
        include_packed = bool(arguments.get('includePacked', False))
        # Determine project directory from the current blend file
        blend_path = Path(self.bpy.data.filepath) if self.bpy.data.filepath else Path.cwd()
        project_dir = blend_path.parent if blend_path.suffix == '.blend' else blend_path
        manifest = generate_manifest(self.bpy, project_dir)
        if not include_packed:
            # Filter out packed files (they don't need to be listed as external deps)
            manifest['dependencies'] = [
                d for d in manifest['dependencies']
                if d['accessible'] or d.get('warning')
            ]
            # Recompute summary
            by_kind = {}
            accessible = 0
            inaccessible = 0
            for dep in manifest['dependencies']:
                kind = dep['kind']
                by_kind[kind] = by_kind.get(kind, 0) + 1
                if dep['accessible']:
                    accessible += 1
                else:
                    inaccessible += 1
            manifest['summary'] = {
                'total': len(manifest['dependencies']),
                'byKind': by_kind,
                'accessible': accessible,
                'inaccessible': inaccessible,
            }
        return {'changedObjects': [], 'result': manifest}

    def validate_portability(self, arguments):
        """Validate that the project can be packaged to the target directory."""
        target_dir = arguments.get('targetDirectory')
        if not target_dir or not isinstance(target_dir, str):
            raise HarnessError('INVALID_ARGUMENT', 'targetDirectory must be a non-empty string')
        target = Path(target_dir)
        blend_path = Path(self.bpy.data.filepath) if self.bpy.data.filepath else Path.cwd()
        project_dir = blend_path.parent if blend_path.suffix == '.blend' else blend_path
        result = validate_portability(self.bpy, target, project_dir)
        return {'changedObjects': [], 'result': result}

    def package_project(self, arguments):
        """Package the project into a self-contained directory.

        Writes only into a new directory; never modifies the active project.
        Refuses to overwrite an existing directory.
        """
        target_dir = arguments.get('targetDirectory')
        if not target_dir or not isinstance(target_dir, str):
            raise HarnessError('INVALID_ARGUMENT', 'targetDirectory must be a non-empty string')
        include_caches = bool(arguments.get('includeCaches', False))
        include_proxies = bool(arguments.get('includeProxies', False))
        target = Path(target_dir)
        blend_path = Path(self.bpy.data.filepath) if self.bpy.data.filepath else Path.cwd()
        if blend_path.suffix != '.blend':
            raise HarnessError('INVALID_ARGUMENT', 'project must be saved as a .blend file before packaging')
        source_project = blend_path
        receipt = package_project(
            self.bpy,
            source_project,
            target,
            include_caches=include_caches,
            include_proxies=include_proxies,
        )
        return {'changedObjects': [], 'result': receipt}
