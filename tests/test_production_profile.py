"""Tests for the evidence-gated production profile.

Five mandatory behaviours:
  1. A production command needs Skill + runtime + visual + delivery evidence.
  2. L4 additionally needs recovery and compatibility evidence.
  3. expert / experimental classes do not enter the production catalog.
  4. The optional official uploader cannot block core ready.
  5. A declared evidence path that does not exist makes the validator fail.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.harness.production_profile import ProductionProfile, RuntimeIdentity
from scripts.harness.registry import CommandRegistry
from scripts.harness.commands.validation import closed_arguments


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(config, tmpdir: Path) -> Path:
    """Write a production-profile JSON and return its path."""
    path = tmpdir / 'production-profile.json'
    path.write_text(json.dumps(config))
    return path


def _identity(runtime_mode: str = 'managed') -> RuntimeIdentity:
    return RuntimeIdentity(
        blender_version=(5, 2, 1),
        platform='darwin',
        architecture='arm64',
        runtime_mode=runtime_mode,
    )


def _registry_with_l3():
    """A registry containing one L3 command with full evidence."""
    reg = CommandRegistry()
    reg.register('mesh.inspect', lambda _: {}, risk='read',
                 metadata={'domain': 'mesh', 'maturity': 'L3',
                           'skills': ['blender-inspect'],
                           'verification': {
                               'runtime': ['tests/runtime/p1_foundation_smoke.py'],
                               'visual': ['docs/verification/blender-domain-coverage-matrix.md'],
                               'delivery': ['tests/runtime/p1_delivery_acceptance.py'],
                           }})
    return reg


def _registry_with_l4():
    """A registry containing one L4 command with full evidence."""
    reg = CommandRegistry()
    reg.register('rig.rigify_install', lambda _: {}, risk='gated',
                 metadata={'domain': 'rig', 'maturity': 'L4',
                           'skills': ['blender-character-rigging'],
                           'verification': {
                               'runtime': ['tests/runtime/p9_rigify_install_acceptance.py'],
                               'visual': ['docs/verification/windows-l4-rigify.md'],
                               'delivery': ['tests/runtime/p9_rigify_install_acceptance.py'],
                               'recoveryAndCompatibility': ['docs/verification/windows-l4-rigify.md'],
                           }})
    return reg


def _registry_with_optional():
    """A registry with a core L3 command and an optional official_uploader."""
    reg = CommandRegistry()
    reg.register('mesh.inspect', lambda _: {}, risk='read',
                 metadata={'domain': 'mesh', 'maturity': 'L3',
                           'skills': ['blender-inspect'],
                           'verification': {
                               'runtime': ['tests/runtime/p1_foundation_smoke.py'],
                               'visual': ['docs/verification/blender-domain-coverage-matrix.md'],
                               'delivery': ['tests/runtime/p1_delivery_acceptance.py'],
                           }})
    reg.register('official_uploader.status', lambda _: {}, risk='read',
                 metadata={'domain': 'official_uploader', 'maturity': 'L1',
                           'skills': ['codex-blender-jimeng-web']})
    return reg


class _TmpdirMixin:
    """Provides a temporary directory that is cleaned up after each test."""
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class ProductionProfileVerdictTests(_TmpdirMixin, unittest.TestCase):
    """Behaviour 1: production command needs Skill + runtime + visual + delivery.

    The registration-time gate already rejects L3/L4 without evidence.
    The production profile verifies the evidence that made it through
    registration and checks path existence.
    """

    def test_l3_with_all_evidence_is_ready(self):
        reg = _registry_with_l3()
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('mesh.inspect', _identity(), reg)
        self.assertEqual(verdict.status, 'ready')
        self.assertEqual(verdict.maturity, 'L3')
        self.assertEqual(verdict.missing_evidence, ())

    def test_l1_not_production(self):
        """L1 does not qualify for production -- behaviour 1 core check."""
        reg = CommandRegistry()
        reg.register('scene.inspect', lambda _: {}, risk='read',
                     metadata={'domain': 'scene', 'maturity': 'L1',
                               'skills': ['blender-inspect']})
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('scene.inspect', _identity(), reg)
        self.assertEqual(verdict.status, 'not_production')
        self.assertEqual(verdict.maturity, 'L1')

    def test_l2_not_production(self):
        """L2 does not qualify for production."""
        reg = CommandRegistry()
        reg.register('recipe.desktop_speaker', lambda _: {}, risk='standard',
                     metadata={'domain': 'recipe', 'maturity': 'L2',
                               'skills': ['blender-hard-surface']})
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('recipe.desktop_speaker', _identity(), reg)
        self.assertEqual(verdict.status, 'not_production')
        self.assertEqual(verdict.maturity, 'L2')

    def test_l3_with_all_four_evidence_types_is_ready(self):
        """Verifies all four evidence types are required for L3."""
        reg = _registry_with_l3()
        cap = reg.describe_capability({'id': 'mesh.inspect'})
        self.assertTrue(cap['skills'])
        self.assertTrue(cap['verification']['runtime'])
        self.assertTrue(cap['verification']['visual'])
        self.assertTrue(cap['verification']['delivery'])
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('mesh.inspect', _identity(), reg)
        self.assertEqual(verdict.status, 'ready')


class ProductionProfileL4Tests(_TmpdirMixin, unittest.TestCase):
    """Behaviour 2: L4 additionally needs recovery and compatibility evidence."""

    def test_l4_with_all_evidence_is_ready(self):
        reg = _registry_with_l4()
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('rig.rigify_install', _identity(), reg)
        self.assertEqual(verdict.status, 'ready')
        self.assertEqual(verdict.maturity, 'L4')

    def test_l4_has_recovery_and_compatibility_evidence(self):
        """L4 must carry recoveryAndCompatibility -- verified via describe."""
        reg = _registry_with_l4()
        cap = reg.describe_capability({'id': 'rig.rigify_install'})
        self.assertTrue(cap['verification']['recoveryAndCompatibility'])
        self.assertEqual(cap['maturity'], 'L4')

    def test_l4_profile_requires_recovery_evidence_present(self):
        """The production profile checks that L4 recovery evidence exists."""
        reg = _registry_with_l4()
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('rig.rigify_install', _identity(), reg)
        # All evidence paths exist in the repo, so should be ready.
        self.assertEqual(verdict.status, 'ready')


class ProductionProfileExclusionTests(_TmpdirMixin, unittest.TestCase):
    """Behaviour 3: expert / experimental do not enter the production catalog."""

    def test_expert_class_is_excluded(self):
        reg = CommandRegistry()
        reg.register('advanced.execute_python', lambda _: {}, risk='gated',
                     metadata={'domain': 'advanced', 'maturity': 'L1',
                               'skills': ['codex-blender-use'],
                               'class': 'expert'})
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('advanced.execute_python', _identity(), reg)
        self.assertEqual(verdict.status, 'excluded')

    def test_experimental_class_is_excluded(self):
        reg = CommandRegistry()
        reg.register('experimental.test', lambda _: {}, risk='standard',
                     metadata={'domain': 'experimental', 'maturity': 'L1',
                               'skills': ['codex-blender-use'],
                               'class': 'experimental'})
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('experimental.test', _identity(), reg)
        self.assertEqual(verdict.status, 'excluded')

    def test_explicit_exclude_in_profile(self):
        reg = CommandRegistry()
        reg.register('mesh.inspect', lambda _: {}, risk='read',
                     metadata={'domain': 'mesh', 'maturity': 'L3',
                               'skills': ['blender-inspect'],
                               'verification': {
                                   'runtime': ['tests/runtime/p1_foundation_smoke.py'],
                                   'visual': ['docs/verification/blender-domain-coverage-matrix.md'],
                                   'delivery': ['tests/runtime/p1_delivery_acceptance.py'],
                               }})
        profile_config = {'excludeDomains': ['mesh']}
        profile = ProductionProfile.load(_make_profile(profile_config, self.tmpdir))
        verdict = profile.verdict('mesh.inspect', _identity(), reg)
        self.assertEqual(verdict.status, 'excluded')

    def test_standard_class_enters_catalog(self):
        """A standard-class L3 command is not excluded."""
        reg = _registry_with_l3()
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('mesh.inspect', _identity(), reg)
        self.assertNotEqual(verdict.status, 'excluded')

    def test_status_excludes_expert_from_production_commands(self):
        """expert commands appear nowhere in productionCommands."""
        reg = CommandRegistry()
        reg.register('advanced.execute_python', lambda _: {}, risk='gated',
                     metadata={'domain': 'advanced', 'maturity': 'L1',
                               'skills': ['codex-blender-use'],
                               'class': 'expert'})
        reg.register('mesh.inspect', lambda _: {}, risk='read',
                     metadata={'domain': 'mesh', 'maturity': 'L3',
                               'skills': ['blender-inspect'],
                               'verification': {
                                   'runtime': ['tests/runtime/p1_foundation_smoke.py'],
                                   'visual': ['docs/verification/blender-domain-coverage-matrix.md'],
                                   'delivery': ['tests/runtime/p1_delivery_acceptance.py'],
                               }})
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        status = profile.status(_identity(), reg)
        self.assertNotIn('advanced.execute_python', status['productionCommands'])
        self.assertIn('mesh.inspect', status['productionCommands'])


class ProductionProfileOptionalTests(_TmpdirMixin, unittest.TestCase):
    """Behaviour 4: optional official uploader cannot block core ready."""

    def test_optional_excluded_does_not_block_core(self):
        reg = _registry_with_optional()
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        status = profile.status(_identity(), reg)
        self.assertEqual(status['status'], 'ready')
        self.assertIn('mesh.inspect', status['productionCommands'])

    def test_optional_commands_flagged_separately(self):
        reg = _registry_with_optional()
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        status = profile.status(_identity(), reg)
        self.assertIn('official_uploader.status', status['optionalCommands'])

    def test_optional_not_in_blocked(self):
        reg = _registry_with_optional()
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        status = profile.status(_identity(), reg)
        self.assertNotIn('official_uploader.status', status.get('blockedCommands', []))


class ProductionProfileEvidencePathTests(_TmpdirMixin, unittest.TestCase):
    """Behaviour 5: declared evidence path that does not exist fails validation."""

    def test_missing_evidence_path_blocks(self):
        """A declared path that does not exist on disk must block the command."""
        reg = CommandRegistry()
        reg.register('mesh.inspect', lambda _: {}, risk='read',
                     metadata={'domain': 'mesh', 'maturity': 'L3',
                               'skills': ['blender-inspect'],
                               'verification': {
                                   'runtime': ['tests/runtime/NONEXISTENT_FILE.py'],
                                   'visual': ['docs/verification/blender-domain-coverage-matrix.md'],
                                   'delivery': ['tests/runtime/p1_delivery_acceptance.py'],
                               }})
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('mesh.inspect', _identity(), reg)
        self.assertEqual(verdict.status, 'blocked')
        self.assertTrue(len(verdict.missing_evidence) > 0)

    def test_all_evidence_paths_exist(self):
        reg = _registry_with_l3()
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('mesh.inspect', _identity(), reg)
        self.assertEqual(verdict.status, 'ready')
        self.assertEqual(verdict.missing_evidence, ())

    def test_missing_delivery_path_blocks(self):
        reg = CommandRegistry()
        reg.register('mesh.inspect', lambda _: {}, risk='read',
                     metadata={'domain': 'mesh', 'maturity': 'L3',
                               'skills': ['blender-inspect'],
                               'verification': {
                                   'runtime': ['tests/runtime/p1_foundation_smoke.py'],
                                   'visual': ['docs/verification/blender-domain-coverage-matrix.md'],
                                   'delivery': ['tests/runtime/NONEXISTENT_DELIVERY.py'],
                               }})
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('mesh.inspect', _identity(), reg)
        self.assertEqual(verdict.status, 'blocked')

    def test_l4_missing_recovery_path_blocks(self):
        reg = CommandRegistry()
        reg.register('rig.rigify_install', lambda _: {}, risk='gated',
                     metadata={'domain': 'rig', 'maturity': 'L4',
                               'skills': ['blender-character-rigging'],
                               'verification': {
                                   'runtime': ['tests/runtime/p9_rigify_install_acceptance.py'],
                                   'visual': ['docs/verification/windows-l4-rigify.md'],
                                   'delivery': ['tests/runtime/p9_rigify_install_acceptance.py'],
                                   'recoveryAndCompatibility': ['docs/verification/NONEXISTENT_RECOVERY.md'],
                               }})
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('rig.rigify_install', _identity(), reg)
        self.assertEqual(verdict.status, 'blocked')


class ProductionProfileL1CommandsTests(_TmpdirMixin, unittest.TestCase):
    """Tests for l1Commands in production status output."""

    def test_l1_commands_tracked_in_status(self):
        """L1 commands that are not excluded or optional appear in l1Commands."""
        reg = CommandRegistry()
        reg.register('playback.set', lambda _: {}, risk='read',
                     metadata={'domain': 'playback', 'maturity': 'L1',
                               'skills': ['codex-blender-use']})
        reg.register('mesh.inspect', lambda _: {}, risk='read',
                     metadata={'domain': 'mesh', 'maturity': 'L3',
                               'skills': ['blender-inspect'],
                               'verification': {
                                   'runtime': ['tests/runtime/p1_foundation_smoke.py'],
                                   'visual': ['docs/verification/blender-domain-coverage-matrix.md'],
                                   'delivery': ['tests/runtime/p1_delivery_acceptance.py'],
                               }})
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        status = profile.status(_identity(), reg)
        self.assertIn('playback.set', status['l1Commands'])
        self.assertNotIn('mesh.inspect', status['l1Commands'])
        self.assertIn('mesh.inspect', status['productionCommands'])

    def test_expert_excluded_from_l1_commands(self):
        """expert-class L1 commands do not appear in l1Commands."""
        reg = CommandRegistry()
        reg.register('advanced.execute_python', lambda _: {}, risk='gated',
                     metadata={'domain': 'advanced', 'maturity': 'L1',
                               'skills': ['codex-blender-use'],
                               'class': 'expert'})
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        status = profile.status(_identity(), reg)
        self.assertNotIn('advanced.execute_python', status['l1Commands'])

    def test_optional_excluded_from_l1_commands(self):
        """Optional domain L1 commands do not appear in l1Commands."""
        reg = CommandRegistry()
        reg.register('official_uploader.status', lambda _: {}, risk='read',
                     metadata={'domain': 'official_uploader', 'maturity': 'L1',
                               'skills': ['codex-blender-jimeng-web']})
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        status = profile.status(_identity(), reg)
        self.assertNotIn('official_uploader.status', status['l1Commands'])
        self.assertIn('official_uploader.status', status['optionalCommands'])


class ProductionProfileStatusTests(_TmpdirMixin, unittest.TestCase):
    """Tests for production.status and catalogHash."""

    def test_status_returns_catalog_hash(self):
        reg = _registry_with_l3()
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        status = profile.status(_identity(), reg)
        self.assertIn('catalogHash', status)
        self.assertIsInstance(status['catalogHash'], str)
        self.assertTrue(len(status['catalogHash']) > 0)

    def test_catalog_hash_is_deterministic(self):
        reg = _registry_with_l3()
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        h1 = profile.status(_identity(), reg)['catalogHash']
        h2 = profile.status(_identity(), reg)['catalogHash']
        self.assertEqual(h1, h2)

    def test_catalog_hash_changes_with_profile_content(self):
        reg = _registry_with_l3()
        p1 = ProductionProfile.load(_make_profile({}, self.tmpdir))
        p2 = ProductionProfile.load(_make_profile({'excludeDomains': ['mesh']}, self.tmpdir))
        h1 = p1.status(_identity(), reg)['catalogHash']
        h2 = p2.status(_identity(), reg)['catalogHash']
        self.assertNotEqual(h1, h2)

    def test_unregistered_command_verdict(self):
        reg = CommandRegistry()
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        verdict = profile.verdict('nonexistent.command', _identity(), reg)
        self.assertEqual(verdict.status, 'blocked')

    def test_status_has_expected_keys(self):
        reg = _registry_with_l3()
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        status = profile.status(_identity(), reg)
        self.assertIn('status', status)
        self.assertIn('productionCommands', status)
        self.assertIn('optionalCommands', status)
        self.assertIn('blockedCommands', status)
        self.assertIn('l1Commands', status)
        self.assertIn('catalogHash', status)

    def test_status_blocked_when_evidence_missing(self):
        reg = CommandRegistry()
        reg.register('mesh.inspect', lambda _: {}, risk='read',
                     metadata={'domain': 'mesh', 'maturity': 'L3',
                               'skills': ['blender-inspect'],
                               'verification': {
                                   'runtime': ['tests/runtime/NONEXISTENT.py'],
                                   'visual': ['docs/verification/blender-domain-coverage-matrix.md'],
                                   'delivery': ['tests/runtime/p1_delivery_acceptance.py'],
                               }})
        profile = ProductionProfile.load(_make_profile({}, self.tmpdir))
        status = profile.status(_identity(), reg)
        self.assertEqual(status['status'], 'blocked')
        self.assertIn('mesh.inspect', status['blockedCommands'])


class BackwardCompatibilityTests(unittest.TestCase):
    """capability.list/describe with no new args must return the same shape."""

    def test_list_no_profile_returns_original_shape(self):
        from scripts.harness.runtime import build_registry
        from tests.test_design_commands import FakeBpy
        reg = build_registry(FakeBpy())
        result = reg.list_capabilities({'limit': 5})
        self.assertIn('items', result)
        self.assertIn('total', result)
        self.assertIn('nextOffset', result)
        self.assertIn('domains', result)
        for item in result['items']:
            self.assertNotIn('productionVerdict', item)

    def test_describe_no_profile_returns_original_shape(self):
        from scripts.harness.runtime import build_registry
        from tests.test_design_commands import FakeBpy
        reg = build_registry(FakeBpy())
        result = reg.describe_capability({'id': 'object.rename'})
        self.assertIn('id', result)
        self.assertIn('maturity', result)
        self.assertIn('verification', result)
        self.assertNotIn('productionVerdict', result)

    def test_list_with_profile_returns_verdict(self):
        """When a profile is provided, items include productionVerdict."""
        import tempfile
        tmpdir = Path(tempfile.mkdtemp())
        try:
            profile_path = tmpdir / 'production-profile.json'
            profile_path.write_text(json.dumps({}))
            from scripts.harness.runtime import build_registry
            from tests.test_design_commands import FakeBpy
            from scripts.harness.production_profile import ProductionProfile, RuntimeIdentity
            reg = build_registry(FakeBpy())
            profile = ProductionProfile.load(profile_path)
            runtime = RuntimeIdentity(
                blender_version=(5, 2, 1), platform='darwin',
                architecture='arm64', runtime_mode='managed')
            result = reg.list_capabilities({'limit': 5, 'profile': profile,
                                            'runtime': runtime})
            self.assertIn('items', result)
            self.assertIn('total', result)
            self.assertIn('nextOffset', result)
            self.assertIn('domains', result)
            for item in result['items']:
                self.assertIn('productionVerdict', item)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_production_domain_is_filterable(self):
        """I1: every domain in the catalog's domains payload must be filterable."""
        from scripts.harness.runtime import build_registry
        from tests.test_design_commands import FakeBpy
        reg = build_registry(FakeBpy())
        catalog = reg.list_capabilities({'limit': 100})
        for domain_name in catalog['domains']:
            # Must not raise INVALID_ARGUMENT for a domain that the catalog advertises.
            result = reg.list_capabilities({'domain': domain_name, 'limit': 100})
            self.assertIn('items', result)

    def test_blenderVersion_platform_runtimeMode_build_identity(self):
        """I2: blenderVersion/platform/runtimeMode are used when profile is given."""
        import tempfile
        tmpdir = Path(tempfile.mkdtemp())
        try:
            profile_path = tmpdir / 'production-profile.json'
            profile_path.write_text(json.dumps({}))
            from scripts.harness.runtime import build_registry
            from tests.test_design_commands import FakeBpy
            from scripts.harness.production_profile import ProductionProfile
            reg = build_registry(FakeBpy())
            profile = ProductionProfile.load(profile_path)
            # Pass blenderVersion/platform/runtimeMode instead of a runtime object.
            result = reg.list_capabilities({
                'limit': 5, 'profile': profile,
                'blenderVersion': [5, 2, 1],
                'platform': 'windows',
                'runtimeMode': 'connector',
            })
            self.assertIn('items', result)
            for item in result['items']:
                self.assertIn('productionVerdict', item)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
