"""Typed rigid-body, cloth, soft-body, collision, fluid and cache controls."""
from pathlib import Path
from ..errors import HarnessError
from ..identity import ObjectResolver
from ..operation_context import OperationContext
from .validation import finite_number,require_name

_BAKE_TYPES = {'CLOTH', 'SOFT_BODY', 'FLUID', 'DYNAMIC_PAINT', 'RIGID_BODY', 'PARTICLE'}


class SimulationCommands:
    def __init__(self,bpy_module,output_root=None):
        self.bpy=bpy_module;self.objects=ObjectResolver(bpy_module);self.context=OperationContext(bpy_module);self.output=Path(output_root).resolve() if output_root else None
    def _cache_path(self,obj):
        if self.output is None:return None
        path=self.output/'simulation-cache'/self.objects.ensure_id(obj);path.mkdir(parents=True,exist_ok=True);return path
    def rigid_body(self,args):
        obj=self.objects.resolve(args,required_type={'MESH'});kind=str(args.get('bodyType','ACTIVE')).upper();shape=str(args.get('collisionShape','CONVEX_HULL')).upper()
        if kind not in {'ACTIVE','PASSIVE'} or shape not in {'BOX','SPHERE','CAPSULE','CYLINDER','CONE','CONVEX_HULL','MESH'}:raise HarnessError('INVALID_ARGUMENT','rigid body type/shape is invalid')
        mass=finite_number(args.get('mass',1),'mass',positive=True)
        with self.context.active_object(obj):
            if obj.rigid_body is None:self.bpy.ops.rigidbody.object_add()
            obj.rigid_body.type=kind;obj.rigid_body.collision_shape=shape;obj.rigid_body.mass=mass
        return {'changedObjects':[obj.name],'result':self.objects.receipt(obj)|{'bodyType':kind,'collisionShape':shape,'mass':mass}}
    def collision(self,args):
        obj=self.objects.resolve(args,required_type={'MESH'});thickness=finite_number(args.get('thickness',.015),'thickness',minimum=0)
        with self.context.active_object(obj):
            if not any(m.type=='COLLISION' for m in obj.modifiers):self.bpy.ops.object.modifier_add(type='COLLISION')
        if getattr(obj,'collision',None):obj.collision.thickness_outer=thickness
        return {'changedObjects':[obj.name],'result':self.objects.receipt(obj)|{'thickness':thickness}}
    def cloth(self,args):
        obj=self.objects.resolve(args,required_type={'MESH'});name=require_name(args.get('modifierName','Cloth'))
        quality=args.get('quality',5);mass=finite_number(args.get('mass',.3),'mass',positive=True)
        if type(quality) is not int or not 1<=quality<=80:raise HarnessError('INVALID_ARGUMENT','quality must be 1..80')
        if obj.modifiers.get(name):raise HarnessError('NAME_COLLISION','modifier already exists')
        modifier=obj.modifiers.new(name=name,type='CLOTH');modifier.settings.quality=quality;modifier.settings.mass=mass
        self._configure_cache(obj,modifier.point_cache,args)
        return {'changedObjects':[obj.name],'result':self.objects.receipt(obj)|{'modifierName':name,'cache':self._cache_receipt(modifier.point_cache)}}
    def soft_body(self,args):
        obj=self.objects.resolve(args,required_type={'MESH'});name=require_name(args.get('modifierName','Soft Body'))
        if obj.modifiers.get(name):raise HarnessError('NAME_COLLISION','modifier already exists')
        before=set(obj.modifiers)
        with self.context.active_object(obj):self.bpy.ops.object.modifier_add(type='SOFT_BODY')
        modifier=next(m for m in obj.modifiers if m not in before and m.type=='SOFT_BODY')
        modifier.name=name;self._configure_cache(obj,modifier.point_cache,args)
        return {'changedObjects':[obj.name],'result':self.objects.receipt(obj)|{'modifierName':name,'cache':self._cache_receipt(modifier.point_cache)}}
    def _configure_cache(self,obj,cache,args):
        start,end=args.get('frameStart',1),args.get('frameEnd',50)
        if type(start) is not int or type(end) is not int or start>end:raise HarnessError('INVALID_ARGUMENT','cache frame range is invalid')
        cache.frame_start=start;cache.frame_end=end
        path=self._cache_path(obj)
        if path:cache.filepath=str(path)
    @staticmethod
    def _cache_receipt(cache):return {'frameStart':cache.frame_start,'frameEnd':cache.frame_end,'filepath':cache.filepath,'isBaked':bool(cache.is_baked)}
    def quick_smoke(self,args):
        flows=args.get('flows')
        if not isinstance(flows,list) or not flows:raise HarnessError('INVALID_ARGUMENT','flows must contain object locators')
        resolution=args.get('resolution',32);start=args.get('frameStart',1);end=args.get('frameEnd',50)
        if type(resolution) is not int or not 16<=resolution<=256:raise HarnessError('INVALID_ARGUMENT','resolution must be 16..256')
        if type(start) is not int or type(end) is not int or start>end:raise HarnessError('INVALID_ARGUMENT','frame range is invalid')
        objects=[self.objects.resolve(locator,required_type={'MESH'}) for locator in flows];before=set(self.bpy.data.objects)
        with self.context.active_objects(objects,active=objects[0]):
            properties={item.identifier for item in self.bpy.ops.object.quick_smoke.get_rna_type().properties}
            options={'style':'SMOKE'}
            if 'show_flows' in properties:options['show_flows']=True
            elif 'render' in properties:options['render']=False
            result=self.bpy.ops.object.quick_smoke(**options)
            if result!={'FINISHED'}:raise HarnessError('OPERATION_FAILED','quick smoke did not finish')
        created=[obj for obj in self.bpy.data.objects if obj not in before];domain=next((obj for obj in created if any(m.type=='FLUID' and m.fluid_type=='DOMAIN' for m in obj.modifiers)),None)
        if domain is None:raise HarnessError('OPERATION_FAILED','smoke domain was not created')
        modifier=next(m for m in domain.modifiers if m.type=='FLUID');settings=modifier.domain_settings
        settings.resolution_max=resolution
        settings.cache_frame_start=start;settings.cache_frame_end=end
        path=self._cache_path(domain)
        if path:settings.cache_directory=str(path)
        return {'changedObjects':[obj.name for obj in [*objects,domain]],'result':{'domain':self.objects.receipt(domain),
          'flows':[self.objects.receipt(obj) for obj in objects],'resolution':resolution,'cacheDirectory':settings.cache_directory}}
    def _caches(self,obj):
        caches=[]
        for modifier in obj.modifiers:
            cache=getattr(modifier,'point_cache',None)
            if cache:caches.append((modifier.name,cache))
        return caches
    def cache_status(self,args):
        obj=self.objects.resolve(args);items=[{'modifierName':name,**self._cache_receipt(cache)} for name,cache in self._caches(obj)]
        for modifier in obj.modifiers:
            settings=getattr(modifier,'domain_settings',None)
            if settings:items.append({'modifierName':modifier.name,'frameStart':settings.cache_frame_start,'frameEnd':settings.cache_frame_end,
              'filepath':settings.cache_directory,'isBaked':bool(getattr(settings,'has_cache_baked_any',False) or getattr(settings,'cache_status',None)=='BAKED')})
        return {'changedObjects':[],'result':self.objects.receipt(obj)|{'caches':items}}
    def free_cache(self,args):
        obj=self.objects.resolve(args);freed=[]
        for name,cache in self._caches(obj):
            if cache.is_baked:
                try:
                    with self.bpy.context.temp_override(point_cache=cache):self.bpy.ops.ptcache.free_bake()
                    freed.append(name)
                except Exception as exc:raise HarnessError('OPERATION_FAILED',f'could not free cache: {name}') from exc
        for modifier in obj.modifiers:
            settings=getattr(modifier,'domain_settings',None)
            if settings and (getattr(settings,'has_cache_baked_any',False) or getattr(settings,'cache_status',None)=='BAKED'):
                hidden=(obj.hide_viewport,obj.hide_render,obj.hide_get())
                try:
                    obj.hide_viewport=False;obj.hide_render=False;obj.hide_set(False)
                    with self.context.active_object(obj):self.bpy.ops.fluid.free_all()
                    freed.append(modifier.name)
                except Exception as exc:raise HarnessError('OPERATION_FAILED',f'could not free fluid cache: {modifier.name}') from exc
                finally:
                    obj.hide_viewport,obj.hide_render=hidden[0],hidden[1];obj.hide_set(hidden[2])
        return {'changedObjects':[obj.name] if freed else [],'result':{'object':self.objects.receipt(obj),'freed':freed}}

    def bake(self, args):
        """Bake a point-cache simulation type for an object.

        Parameters
        ----------
        objectId : str
            Object locator.
        bakeType : str
            One of: CLOTH, SOFT_BODY, FLUID, DYNAMIC_PAINT, RIGID_BODY,
            PARTICLE.  Determines which modifier cache is baked.
        frameStart : int
            First frame of the bake range (inclusive).
        frameEnd : int
            Last frame of the bake range (inclusive).

        Behaviour:
        * For CLOTH/SOFT_BODY, locates the matching modifier's point cache,
          sets the frame range, and calls ``ptcache.bake``.
        * For FLUID, locates the fluid domain modifier's domain settings and
          calls ``fluid.bake_all``.
        * If the cache is already baked, it is freed first.
        * If the bake target object is hidden or the modifier is disabled,
          the command unlocks visibility before baking and restores it after.
        """
        oid = args.get('objectId')
        obj = self.objects.resolve(oid if isinstance(oid, dict) else {'objectId': oid})
        bake_type = str(args.get('bakeType', '')).upper()
        if bake_type not in _BAKE_TYPES:
            raise HarnessError('INVALID_ARGUMENT', f'bakeType must be one of {sorted(_BAKE_TYPES)}')
        frame_start = args.get('frameStart', 1)
        frame_end = args.get('frameEnd', 50)
        if type(frame_start) is not int or type(frame_end) is not int or frame_start > frame_end:
            raise HarnessError('INVALID_ARGUMENT', 'frame range is invalid')

        baked = []
        cancelled = False

        if bake_type in ('CLOTH', 'SOFT_BODY', 'RIGID_BODY', 'PARTICLE', 'DYNAMIC_PAINT'):
            # Find matching point caches
            for mod_name, cache in self._caches(obj):
                # Attempt to match type by modifier type
                mod = obj.modifiers.get(mod_name)
                if mod is None:
                    continue
                type_match = {
                    'CLOTH': 'CLOTH', 'SOFT_BODY': 'SOFT_BODY',
                    'RIGID_BODY': 'RIGID_BODY', 'PARTICLE': 'PARTICLE_SYSTEM',
                    'DYNAMIC_PAINT': 'DYNAMIC_PAINT',
                }.get(bake_type)
                if mod.type != type_match:
                    continue
                # Free if already baked
                if cache.is_baked:
                    try:
                        with self.bpy.context.temp_override(point_cache=cache):
                            self.bpy.ops.ptcache.free_bake()
                    except Exception:
                        pass
                cache.frame_start = frame_start
                cache.frame_end = frame_end
                # Unlock object visibility if needed
                hidden = (obj.hide_viewport, obj.hide_render, obj.hide_get())
                try:
                    obj.hide_viewport = False
                    obj.hide_render = False
                    obj.hide_set(False)
                    with self.bpy.context.temp_override(point_cache=cache):
                        self.bpy.ops.ptcache.bake(bake=True)
                    baked.append(mod_name)
                except Exception as exc:
                    cancelled = True
                finally:
                    obj.hide_viewport, obj.hide_render = hidden[0], hidden[1]
                    obj.hide_set(hidden[2])

        elif bake_type == 'FLUID':
            for mod in obj.modifiers:
                if mod.type != 'FLUID':
                    continue
                settings = getattr(mod, 'domain_settings', None)
                if settings is None:
                    continue
                settings.cache_frame_start = frame_start
                settings.cache_frame_end = frame_end
                hidden = (obj.hide_viewport, obj.hide_render, obj.hide_get())
                try:
                    obj.hide_viewport = False
                    obj.hide_render = False
                    obj.hide_set(False)
                    with self.context.active_object(obj):
                        self.bpy.ops.fluid.bake_all()
                    baked.append(mod.name)
                except Exception as exc:
                    cancelled = True
                finally:
                    obj.hide_viewport, obj.hide_render = hidden[0], hidden[1]
                    obj.hide_set(hidden[2])

        return {'changedObjects': [obj.name] if baked else [], 'result': {
            'object': self.objects.receipt(obj),
            'bakeType': bake_type,
            'frameStart': frame_start,
            'frameEnd': frame_end,
            'baked': baked,
            'cancelled': cancelled,
        }}

    def validate(self, args):
        """Validate simulation caches against requested metrics.

        Parameters
        ----------
        objectId : str
            Object locator.
        metrics : dict, optional
            What to check.  Keys (all optional, all default to True):
            * ``framesBaked`` (bool) -- report how many frames are baked.
            * ``rangeCoverage`` (bool) -- check whether the baked range
              covers the requested frameStart..frameEnd.
            * ``staleness`` (bool) -- detect if the cache is stale
              (baked range does not match the modifier's current range).

        Returns
        -------
        dict with ``passed`` and ``caches``, where each cache entry has:
            * ``modifierName`` (str)
            * ``framesBaked`` (int) -- number of baked frames (0 if not baked).
            * ``requestedRange`` (dict) -- {frameStart, frameEnd} from the
              modifier's current point-cache settings.
            * ``bakedRange`` (dict | null) -- {frameStart, frameEnd} that was
              actually baked, or null if not baked.
            * ``rangeCoverage`` (float) -- fraction of requested frames that
              are covered by the baked range (0.0 to 1.0).
            * ``stale`` (bool) -- True if the baked range differs from the
              modifier's configured range.
        """
        oid = args.get('objectId')
        obj = self.objects.resolve(oid if isinstance(oid, dict) else {'objectId': oid})
        metrics_arg = args.get('metrics') or {}
        check_frames = metrics_arg.get('framesBaked', True)
        check_coverage = metrics_arg.get('rangeCoverage', True)
        check_staleness = metrics_arg.get('staleness', True)

        caches_result = []
        all_passed = True

        for mod_name, cache in self._caches(obj):
            entry = {'modifierName': mod_name}
            is_baked = bool(cache.is_baked)
            requested_start = cache.frame_start
            requested_end = cache.frame_end

            if check_frames:
                if is_baked:
                    # Count baked frames by reading the baked frame range
                    baked_start = getattr(cache, 'frame_start', requested_start)
                    baked_end = getattr(cache, 'frame_end', requested_end)
                    entry['framesBaked'] = baked_end - baked_start + 1
                else:
                    entry['framesBaked'] = 0

            if check_coverage:
                entry['requestedRange'] = {'frameStart': requested_start, 'frameEnd': requested_end}
                if is_baked:
                    baked_start = getattr(cache, 'frame_start', requested_start)
                    baked_end = getattr(cache, 'frame_end', requested_end)
                    entry['bakedRange'] = {'frameStart': baked_start, 'frameEnd': baked_end}
                    requested_count = max(requested_end - requested_start + 1, 1)
                    covered_start = max(baked_start, requested_start)
                    covered_end = min(baked_end, requested_end)
                    covered = max(covered_end - covered_start + 1, 0)
                    entry['rangeCoverage'] = round(covered / requested_count, 6)
                else:
                    entry['bakedRange'] = None
                    entry['rangeCoverage'] = 0.0
                    all_passed = False

            if check_staleness:
                if is_baked:
                    baked_start = getattr(cache, 'frame_start', requested_start)
                    baked_end = getattr(cache, 'frame_end', requested_end)
                    entry['stale'] = (baked_start != requested_start or baked_end != requested_end)
                    if entry['stale']:
                        all_passed = False
                else:
                    entry['stale'] = True
                    all_passed = False

            caches_result.append(entry)

        # Also check fluid domain caches
        for mod in obj.modifiers:
            settings = getattr(mod, 'domain_settings', None)
            if settings is None:
                continue
            entry = {'modifierName': mod.name + ' (fluid)'}
            is_baked = bool(getattr(settings, 'has_cache_baked_any', False) or
                            getattr(settings, 'cache_status', None) == 'BAKED')
            requested_start = settings.cache_frame_start
            requested_end = settings.cache_frame_end

            if check_frames:
                entry['framesBaked'] = (requested_end - requested_start + 1) if is_baked else 0
            if check_coverage:
                entry['requestedRange'] = {'frameStart': requested_start, 'frameEnd': requested_end}
                entry['bakedRange'] = {'frameStart': requested_start, 'frameEnd': requested_end} if is_baked else None
                entry['rangeCoverage'] = 1.0 if is_baked else 0.0
                if not is_baked:
                    all_passed = False
            if check_staleness:
                entry['stale'] = not is_baked
                if not is_baked:
                    all_passed = False

            caches_result.append(entry)

        return {'changedObjects': [], 'result': self.objects.receipt(obj) | {
            'passed': all_passed,
            'caches': caches_result,
        }}
