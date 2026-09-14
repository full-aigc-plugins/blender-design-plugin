import unittest

from scripts.harness.registry import CommandRegistry
from scripts.harness.commands.validation import closed_arguments
from scripts.harness.errors import HarnessError


class CapabilityCatalogTests(unittest.TestCase):
    def registry(self):
        registry = CommandRegistry()
        registry.register('mesh.inspect', lambda _: {}, risk='read',
                          validate=closed_arguments(required=('object',)),
                          metadata={'domain': 'mesh', 'maturity': 'L1',
                                    'skills': [], 'tests': ['unit:test_inspect']})
        registry.register('object.rename', lambda _: {},
                          validate=closed_arguments(required=('name', 'newName')))
        return registry

    def test_legacy_contract_unchanged(self):
        self.assertEqual(self.registry().capabilities(), [
            {'command': 'mesh.inspect', 'risk': 'read'},
            {'command': 'object.rename', 'risk': 'standard'}])

    def test_pagination_and_filter(self):
        registry = self.registry()
        page = registry.list_capabilities({'limit': 1})
        self.assertEqual(len(page['items']), 1)
        self.assertEqual(page['nextOffset'], 1)
        self.assertEqual(registry.list_capabilities({'offset': 1})['nextOffset'], None)
        self.assertEqual(registry.list_capabilities({'domain': 'mesh'})['total'], 1)
        self.assertEqual(registry.list_capabilities({'maturity': 'L3'})['total'], 0)

    def test_description_honest_about_unknown_evidence(self):
        result = self.registry().describe_capability({'id': 'object.rename'})
        self.assertEqual(result['maturity'], 'L1')
        self.assertEqual(result['input']['required'], ['name', 'newName'])
        self.assertEqual(result['verification']['runtime'], [])
        self.assertEqual(result['availability']['status'], 'unknown')

    def test_availability_recomputed_and_metadata_defensive_copy(self):
        enabled = []
        metadata = {'domain': 'mesh', 'skills': ['a']}
        registry = CommandRegistry()
        registry.register('mesh.edit', lambda _: {}, metadata=metadata,
                          availability=lambda: {'status': 'available' if enabled else 'unavailable',
                                                'reason': None if enabled else 'Object mode required'})
        metadata['skills'].append('forged')
        self.assertEqual(registry.describe_capability({'id': 'mesh.edit'})['skills'], ['a'])
        self.assertEqual(registry.describe_capability({'id': 'mesh.edit'})['availability']['status'], 'unavailable')
        enabled.append(True)
        self.assertEqual(registry.describe_capability({'id': 'mesh.edit'})['availability']['status'], 'available')

    def test_invalid_filters_and_unknown_id_fail(self):
        for args in ({'limit': True}, {'limit': 0}, {'offset': -1},
                     {'maturity': 'complete'}, {'unknown': 1}, {'domain': []}):
            with self.subTest(args=args), self.assertRaises(HarnessError):
                self.registry().list_capabilities(args)
        with self.assertRaises(HarnessError):
            self.registry().describe_capability({'id': 'rig.create'})

    def test_l3_requires_runtime_evidence_and_skill(self):
        with self.assertRaises(HarnessError):
            CommandRegistry().register('rig.create', lambda _: {}, metadata={'maturity': 'L3'})

    def test_runtime_only_evidence_cannot_claim_production(self):
        with self.assertRaises(HarnessError):
            CommandRegistry().register('rig.create', lambda _: {}, metadata={
                'maturity': 'L3', 'skills': ['rig'], 'verification': {'runtime': ['smoke']}})

    def test_metadata_cannot_override_identity_or_risk(self):
        for metadata in ({'id': 'fake'}, {'risk': 'read'}, {'input': {}}):
            with self.subTest(metadata=metadata), self.assertRaises(HarnessError):
                CommandRegistry().register('object.delete', lambda _: {}, risk='gated', metadata=metadata)

    def test_probe_failure_is_unknown_not_a_broken_catalog(self):
        registry = CommandRegistry()
        registry.register('mesh.inspect', lambda _: {},
                          availability=lambda: (_ for _ in ()).throw(RuntimeError('private detail')))
        result = registry.list_capabilities({})['items'][0]
        self.assertEqual(result['availability']['status'], 'unknown')
        self.assertNotIn('private detail', str(result))

    def test_runtime_probe_distinguishes_background_and_output_scope(self):
        from types import SimpleNamespace
        from scripts.harness.runtime import build_registry
        from tests.test_design_commands import FakeBpy
        bpy = FakeBpy()
        bpy.app = SimpleNamespace(background=True, version_string='test')
        registry = build_registry(bpy)
        for name in ('view.set', 'view.present', 'playback.set', 'preview.capture'):
            result = registry.describe_capability({'id': name})
            self.assertEqual(result['availability']['status'], 'unavailable', name)
            self.assertTrue(result['availability']['reason'])
        result = registry.describe_capability({'id': 'object.transform'})
        self.assertTrue(result['effects']['sceneMutation'])
        self.assertEqual(result['input']['properties']['location']['type'], 'array')

    def test_session_progress_description_matches_intercepted_arguments(self):
        from scripts.harness.runtime import build_registry
        from tests.test_design_commands import FakeBpy
        registry = build_registry(FakeBpy(), runtime_mode="connector")
        result = registry.describe_capability({'id': 'session.set_progress'})
        self.assertEqual(result['input']['required'], ['stage'])
        self.assertIn('progress', result['input']['properties'])
        upload = registry.describe_capability({'id': 'official_uploader.render_and_link'})
        self.assertTrue(upload['effects']['sceneMutation'])
        submit = registry.describe_capability({'id': 'job.submit'})
        self.assertIn('RENDER_ANIMATION_FRAMES', submit['input']['properties']['kind']['enum'])
        self.assertIn('COMPOSE_VIDEO', submit['input']['properties']['kind']['enum'])
        self.assertTrue(registry.describe_capability({'id':'job.resume'})['effects']['cancellable'])

    def test_runtime_metadata_references_existing_resources_without_l3_claim(self):
        from pathlib import Path
        from scripts.harness.runtime import build_registry
        from tests.test_design_commands import FakeBpy
        root = Path(__file__).resolve().parents[1]
        entries = build_registry(FakeBpy()).list_capabilities({'limit': 100})['items']
        for entry in entries:
            self.assertIsNotNone(entry['input'], entry['id'])
            self.assertTrue(entry['tests'], entry['id'])
            for resource in entry['tests']:
                self.assertTrue((root / resource).is_file(), resource)
            for skill in entry['skills']:
                self.assertTrue((root / 'skills' / skill / 'SKILL.md').is_file(), skill)
            self.assertIn(entry['maturity'], {'L1','L2','L3','L4'})

    def test_windows_verified_recovery_and_rigify_commands_are_l4(self):
        from scripts.harness.runtime import build_registry
        from tests.test_design_commands import FakeBpy
        registry=build_registry(FakeBpy())
        for name in ('job.resume','rig.rigify_install','rig.rigify_generate'):
            capability=registry.describe_capability({'id':name})
            self.assertEqual(capability['maturity'],'L4',name)
            self.assertTrue(capability['verification']['recoveryAndCompatibility'],name)

    def test_unimplemented_domains_are_not_commands(self):
        catalog = self.registry().list_capabilities({})
        self.assertIn('sculpt', catalog['domains'])
        self.assertEqual(catalog['domains']['sculpt']['maturity'], 'L0')
        with self.assertRaises(HarnessError):
            self.registry().dispatch('sculpt.brush', {})

    def test_queries_work_during_readonly_takeover_without_revision_changes(self):
        from scripts.harness.runtime import create_session
        from scripts.harness.execution_policy import ExecutionPolicy
        from tests.test_design_commands import FakeBpy
        from tests.test_foreground_policy import call
        session = create_session(FakeBpy(), 'catalog', execution_policy=ExecutionPolicy.review_only())
        session.pause()
        revision = session.scene_revision
        for command, args in [('capability.list', {}), ('capability.describe', {'id': 'object.rename'})]:
            result = call(session, command, args)
            self.assertEqual(result['status'], 'succeeded', result)
            self.assertEqual(session.scene_revision, revision)
