import unittest

from scripts.harness.runtime import build_registry
from tests.test_design_commands import FakeBpy


class SkillRoutingTests(unittest.TestCase):
    def setUp(self):
        self.registry=build_registry(FakeBpy())

    def skills(self,command):
        return self.registry.describe_capability({'id':command})['skills']

    def test_lifecycle_and_foundation_commands_use_precise_skills(self):
        self.assertEqual(self.skills('scene.inspect'),['blender-inspect'])
        self.assertEqual(self.skills('object.transform'),['blender-scene-assembly'])
        self.assertEqual(self.skills('object.join'),['blender-hard-surface'])
        self.assertEqual(self.skills('object.create_curve'),['blender-curves'])
        self.assertEqual(self.skills('asset.pack_resources'),['blender-render-compositing'])

    def test_animation_camera_validation_and_jobs_do_not_fall_back_to_general_design(self):
        self.assertEqual(self.skills('animation.fcurve_edit'),['blender-character-animation'])
        self.assertEqual(self.skills('camera.follow_path'),['blender-cinematography'])
        self.assertEqual(self.skills('validation.foot_drift'),
                         ['blender-quality-validation','blender-character-animation'])
        self.assertEqual(self.skills('job.submit'),['blender-background-jobs'])
        routing=self.registry.describe_capability({'id':'job.submit'})['skillRouting']['byArguments']['kind']
        self.assertEqual(routing['EXPORT'],['blender-render-compositing'])
        self.assertEqual(routing['RENDER_STILL'],['blender-render-compositing'])
        self.assertEqual(routing['BAKE_POINT_CACHES'],['blender-simulation'])
        self.assertEqual(routing['RENDER_ANIMATION_FRAMES'],
                         ['blender-render-compositing','blender-background-jobs'])
        self.assertEqual(routing['COMPOSE_VIDEO'],
                         ['blender-sequence-editing','blender-background-jobs'])
        self.assertEqual(self.skills('job.resume'),['blender-background-jobs'])
        self.assertNotIn('blender-design',self.skills('advanced.execute_python'))

    def test_split_domains_have_discriminating_skill_names(self):
        self.assertEqual(self.skills('sculpt.brush_stroke'),['blender-sculpt-surface'])
        self.assertEqual(self.skills('hair.create_curves'),['blender-hair'])
        self.assertEqual(self.skills('simulation.cloth'),['blender-simulation'])
        self.assertEqual(self.skills('tracking.solve_camera'),['blender-tracking'])
        self.assertEqual(self.skills('sequence.transition'),['blender-sequence-editing'])
        self.assertEqual(self.skills('rig.rigify_install'),['blender-character-rigging'])

    def test_cross_domain_commands_can_load_multiple_relevant_skills(self):
        self.assertEqual(self.skills('export.extended'),
                         ['blender-export','blender-render-compositing'])
        self.assertEqual(self.skills('recipe.desktop_speaker'),
                         ['blender-hard-surface','blender-uv-material'])

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
