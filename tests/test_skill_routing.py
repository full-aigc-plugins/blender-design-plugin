import unittest

from scripts.harness.runtime import build_registry
from tests.test_design_commands import FakeBpy


class SkillRoutingTests(unittest.TestCase):
    def setUp(self):
        self.registry=build_registry(FakeBpy())

    def skills(self,command):
        return self.registry.describe_capability({'id':command})['skills']

    def test_lifecycle_and_foundation_commands_use_precise_skills(self):
        self.assertEqual(self.skills('scene.inspect'),['codex-blender-inspect'])
        self.assertEqual(self.skills('object.transform'),['codex-blender-scene-assembly'])
        self.assertEqual(self.skills('object.join'),['codex-blender-hard-surface'])
        self.assertEqual(self.skills('object.create_curve'),['codex-blender-curves'])
        self.assertEqual(self.skills('asset.pack_resources'),['codex-blender-render-compositing'])

    def test_animation_camera_validation_and_jobs_do_not_fall_back_to_general_design(self):
        self.assertEqual(self.skills('animation.fcurve_edit'),['codex-blender-character-animation'])
        self.assertEqual(self.skills('camera.follow_path'),['codex-blender-cinematography'])
        self.assertEqual(self.skills('validation.foot_drift'),
                         ['codex-blender-quality-validation','codex-blender-character-animation'])
        self.assertEqual(self.skills('job.submit'),['codex-blender-background-jobs'])
        routing=self.registry.describe_capability({'id':'job.submit'})['skillRouting']['byArguments']['kind']
        self.assertEqual(routing['EXPORT'],['codex-blender-render-compositing'])
        self.assertEqual(routing['RENDER_STILL'],['codex-blender-render-compositing'])
        self.assertEqual(routing['BAKE_POINT_CACHES'],['codex-blender-simulation'])
        self.assertEqual(routing['RENDER_ANIMATION_FRAMES'],
                         ['codex-blender-render-compositing','codex-blender-background-jobs'])
        self.assertEqual(routing['COMPOSE_VIDEO'],
                         ['codex-blender-sequence-editing','codex-blender-background-jobs'])
        self.assertEqual(self.skills('job.resume'),['codex-blender-background-jobs'])
        self.assertNotIn('codex-blender-design',self.skills('advanced.execute_python'))

    def test_split_domains_have_discriminating_skill_names(self):
        self.assertEqual(self.skills('sculpt.brush_stroke'),['codex-blender-sculpt-surface'])
        self.assertEqual(self.skills('hair.create_curves'),['codex-blender-hair'])
        self.assertEqual(self.skills('simulation.cloth'),['codex-blender-simulation'])
        self.assertEqual(self.skills('tracking.solve_camera'),['codex-blender-tracking'])
        self.assertEqual(self.skills('sequence.transition'),['codex-blender-sequence-editing'])
        self.assertEqual(self.skills('rig.rigify_install'),['codex-blender-character-rigging'])

    def test_cross_domain_commands_can_load_multiple_relevant_skills(self):
        self.assertEqual(self.skills('export.extended'),
                         ['codex-blender-export','codex-blender-render-compositing'])
        self.assertEqual(self.skills('recipe.desktop_speaker'),
                         ['codex-blender-hard-surface','codex-blender-uv-material'])

    def test_runtime_evidence_matches_the_command_stage(self):
        tracking=self.registry.describe_capability({'id':'tracking.solve_camera'})['verification']['runtime']
        jobs=self.registry.describe_capability({'id':'job.submit'})['verification']['runtime']
        mesh=self.registry.describe_capability({'id':'mesh.edit'})['verification']['runtime']
        self.assertEqual(tracking,['tests/runtime/p7_tracking_foreground.py'])
        self.assertEqual(jobs,['tests/runtime/p3_job_smoke.py','tests/runtime/p3_foreground_job_bootstrap.py',
                               'tests/runtime/p8_frame_pipeline_acceptance.py'])
        self.assertIn('tests/runtime/p1_mesh_smoke.py',mesh)
        self.assertNotIn('tests/runtime/p1_mesh_smoke.py',tracking)

    def test_skill_coverage_describes_actual_role(self):
        self.assertEqual(self.registry.describe_capability({'id':'recipe.rigged_spear_character'})['skillCoverage'],
                         'composite-workflow')
        self.assertEqual(self.registry.describe_capability({'id':'scene.inspect'})['skillCoverage'],
                         'lifecycle-inspection')
        self.assertEqual(self.registry.describe_capability({'id':'mesh.edit'})['skillCoverage'],
                         'domain-workflow')


if __name__=='__main__':
    unittest.main()
