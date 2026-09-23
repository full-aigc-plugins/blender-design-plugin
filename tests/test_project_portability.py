"""Unit tests for project portability: dependency scanning, path validation,
schema conformance, and command registration."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.harness.dependencies import (
    classify_dependency,
    discover_license,
    validate_path_safety,
    validate_package_path,
)
from scripts.harness.errors import HarnessError
from scripts.validate_document import validate_document


class TestDependencyClassification(unittest.TestCase):
    def test_png_is_IMAGE(self):
        self.assertEqual(classify_dependency(Path('/foo/bar.png')), 'IMAGE')

    def test_exr_is_IMAGE(self):
        self.assertEqual(classify_dependency(Path('/foo/bar.exr')), 'IMAGE')

    def test_udim_tile(self):
        self.assertEqual(classify_dependency(Path('/foo/bar.0001.exr')), 'UDIM')

    def test_font_ttf(self):
        self.assertEqual(classify_dependency(Path('/foo/bar.ttf')), 'FONT')

    def test_font_otf(self):
        self.assertEqual(classify_dependency(Path('/foo/bar.otf')), 'FONT')

    def test_audio_wav(self):
        self.assertEqual(classify_dependency(Path('/foo/bar.wav')), 'AUDIO')

    def test_audio_mp3(self):
        self.assertEqual(classify_dependency(Path('/foo/bar.mp3')), 'AUDIO')

    def test_video_mp4(self):
        self.assertEqual(classify_dependency(Path('/foo/bar.mp4')), 'VIDEO')

    def test_blend_library(self):
        self.assertEqual(classify_dependency(Path('/foo/bar.blend')), 'BLEND_LIBRARY')

    def test_image_sequence(self):
        self.assertEqual(classify_dependency(Path('/foo/bar_0001.png')), 'IMAGE_SEQUENCE')

    def test_simulation_cache_dir(self):
        self.assertEqual(classify_dependency(Path('/foo/blend_cache/bar.bin')), 'SIMULATION_CACHE')

    def test_unknown_is_EXTENSION(self):
        self.assertEqual(classify_dependency(Path('/foo/bar.xyz')), 'EXTENSION')


class TestLicenseDiscovery(unittest.TestCase):
    def test_license_file_found(self):
        with tempfile.TemporaryDirectory() as td:
            license_file = Path(td) / 'LICENSE'
            license_file.write_text('MIT License\nCopyright 2024\n', encoding='utf-8')
            asset = Path(td) / 'texture.png'
            asset.touch()
            result = discover_license(asset)
            self.assertEqual(result, 'MIT License')

    def test_no_license_returns_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            asset = Path(td) / 'texture.png'
            asset.touch()
            result = discover_license(asset)
            self.assertEqual(result, 'unknown')

    def test_license_txt_found(self):
        with tempfile.TemporaryDirectory() as td:
            license_file = Path(td) / 'LICENSE.txt'
            license_file.write_text('Apache 2.0\n', encoding='utf-8')
            asset = Path(td) / 'model.fbx'
            asset.touch()
            result = discover_license(asset)
            self.assertEqual(result, 'Apache 2.0')


class TestPathSafety(unittest.TestCase):
    def test_regular_file_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            asset = project_dir / 'textures' / 'diffuse.png'
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b'fake')
            result = validate_path_safety(asset, project_dir)
            self.assertEqual(result, asset.resolve())

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            real_file = project_dir / 'real.png'
            real_file.write_bytes(b'real')
            link = project_dir / 'link.png'
            os.symlink(str(real_file), str(link))
            with self.assertRaises(HarnessError) as ctx:
                validate_path_safety(link, project_dir, label='test')
            self.assertEqual(ctx.exception.code, 'ASSET_NOT_AUTHORIZED')
            self.assertIn('symlink', str(ctx.exception))

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / 'project'
            project_dir.mkdir()
            outside = Path(td) / 'outside' / 'secret.png'
            outside.parent.mkdir()
            outside.write_bytes(b'secret')
            # Construct a path that tries to escape via ..
            escape_path = project_dir / '..' / 'outside' / 'secret.png'
            with self.assertRaises(HarnessError) as ctx:
                validate_path_safety(escape_path, project_dir, label='test')
            self.assertEqual(ctx.exception.code, 'ASSET_NOT_AUTHORIZED')

    def test_in_project_file_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            subdir = project_dir / 'textures'
            subdir.mkdir()
            asset = subdir / 'normal.png'
            asset.write_bytes(b'data')
            result = validate_path_safety(asset, project_dir)
            self.assertEqual(result, asset.resolve())


class TestPackagePathValidation(unittest.TestCase):
    def test_symlink_component_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / 'project'
            project_dir.mkdir()
            real_dir = Path(td) / 'real_assets'
            real_dir.mkdir()
            real_file = real_dir / 'tex.png'
            real_file.write_bytes(b'data')
            # Create symlink in project dir
            link_dir = project_dir / 'linked'
            os.symlink(str(real_dir), str(link_dir))
            link_file = link_dir / 'tex.png'
            with self.assertRaises(HarnessError) as ctx:
                validate_package_path(link_file, project_dir)
            self.assertEqual(ctx.exception.code, 'ASSET_NOT_AUTHORIZED')
            self.assertIn('symlink', str(ctx.exception))

    def test_escape_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / 'project'
            project_dir.mkdir()
            outside = Path(td) / 'outside.png'
            outside.write_bytes(b'data')
            with self.assertRaises(HarnessError) as ctx:
                validate_package_path(outside, project_dir)
            self.assertEqual(ctx.exception.code, 'ASSET_NOT_AUTHORIZED')


class TestSchemaConformance(unittest.TestCase):
    """Validate the new schemas match the draft-07 closed-object convention."""

    def test_dependency_manifest_valid(self):
        payload = {
            'protocolVersion': 'codex-blender/v1',
            'projectPath': '/tmp/project',
            'generatedAt': '2024-01-01T00:00:00Z',
            'dependencies': [
                {
                    'path': '/tmp/project/texture.png',
                    'relativePath': 'texture.png',
                    'kind': 'IMAGE',
                    'sha256': 'a' * 64,
                    'bytes': 1024,
                    'license': 'MIT',
                    'accessible': True,
                }
            ],
            'summary': {
                'total': 1,
                'byKind': {'IMAGE': 1},
                'accessible': 1,
                'inaccessible': 0,
            },
        }
        errors = validate_document('dependency_manifest', payload)
        self.assertEqual(errors, [], f'Schema errors: {errors}')

    def test_dependency_manifest_rejects_unknown_field(self):
        payload = {
            'protocolVersion': 'codex-blender/v1',
            'projectPath': '/tmp/project',
            'generatedAt': '2024-01-01T00:00:00Z',
            'dependencies': [],
            'summary': {
                'total': 0, 'byKind': {}, 'accessible': 0, 'inaccessible': 0
            },
            'unknownField': True,
        }
        errors = validate_document('dependency_manifest', payload)
        self.assertTrue(errors, 'Should reject unknown field')

    def test_dependency_manifest_rejects_bad_kind(self):
        payload = {
            'protocolVersion': 'codex-blender/v1',
            'projectPath': '/tmp/project',
            'generatedAt': '2024-01-01T00:00:00Z',
            'dependencies': [
                {
                    'path': '/tmp/x', 'kind': 'INVALID_KIND',
                    'sha256': 'a' * 64, 'bytes': 0,
                    'license': 'unknown', 'accessible': False,
                }
            ],
            'summary': {
                'total': 1, 'byKind': {}, 'accessible': 0, 'inaccessible': 1
            },
        }
        errors = validate_document('dependency_manifest', payload)
        self.assertTrue(errors, 'Should reject invalid kind')

    def test_project_package_receipt_valid(self):
        payload = {
            'protocolVersion': 'codex-blender/v1',
            'producer': {'name': 'codex-blender', 'version': '0.3.0'},
            'sourceProject': '/tmp/project.blend',
            'targetDirectory': '/tmp/package',
            'packagePath': '/tmp/package/project.blend',
            'files': [
                {
                    'originalPath': '/tmp/project.blend',
                    'packagedPath': 'project.blend',
                    'sha256': 'a' * 64,
                    'bytes': 100,
                    'license': 'unknown',
                }
            ],
            'manifest': {
                'path': '/tmp/package/dependency_manifest.json',
                'sha256': 'b' * 64,
            },
            'validation': {
                'status': 'passed',
                'checks': ['target_directory_fresh', 'sha256_integrity'],
            },
            'warnings': [],
        }
        errors = validate_document('project_package_receipt', payload)
        self.assertEqual(errors, [], f'Schema errors: {errors}')

    def test_project_package_receipt_rejects_unknown_field(self):
        payload = {
            'protocolVersion': 'codex-blender/v1',
            'producer': {'name': 'codex-blender', 'version': '0.3.0'},
            'sourceProject': '/tmp/project.blend',
            'targetDirectory': '/tmp/package',
            'packagePath': '/tmp/package/project.blend',
            'files': [],
            'manifest': {'path': '/tmp/m.json', 'sha256': 'a' * 64},
            'validation': {'status': 'passed', 'checks': []},
            'warnings': [],
            'extra': True,
        }
        errors = validate_document('project_package_receipt', payload)
        self.assertTrue(errors, 'Should reject unknown field')


class TestCommandRegistration(unittest.TestCase):
    """Three new commands must be registered."""

    def test_dependencies_registered(self):
        from tests.test_design_commands import FakeBpy
        from scripts.harness.runtime import build_registry
        bpy = FakeBpy()
        # FakeBpy needs filepath, images, fonts, libraries, movieclips, sounds
        bpy.data.filepath = '/tmp/test.blend'
        bpy.data.images = []
        bpy.data.fonts = []
        bpy.data.libraries = []
        bpy.data.movieclips = []
        bpy.data.sounds = []
        registry = build_registry(bpy)
        caps = {c['command'] for c in registry.capabilities()}
        self.assertIn('asset.dependencies', caps)
        self.assertIn('asset.validate_portability', caps)
        self.assertIn('asset.package_project', caps)

    def test_dependencies_is_read_risk(self):
        from tests.test_design_commands import FakeBpy
        from scripts.harness.runtime import build_registry
        bpy = FakeBpy()
        bpy.data.filepath = '/tmp/test.blend'
        bpy.data.images = []
        bpy.data.fonts = []
        bpy.data.libraries = []
        bpy.data.movieclips = []
        bpy.data.sounds = []
        registry = build_registry(bpy)
        caps = {c['command']: c['risk'] for c in registry.capabilities()}
        self.assertEqual(caps['asset.dependencies'], 'read')
        self.assertEqual(caps['asset.validate_portability'], 'read')


if __name__ == '__main__':
    unittest.main()
