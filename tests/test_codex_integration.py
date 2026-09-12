"""Integration tests: our driver must delegate to the vendored add-on.

These tests run the REAL vendored operator code (``JIMENG_OT_render_upload`` and
``JIMENG_OT_upload_existing``) through a fake ``bpy``. They exist to prove the
integration principle in ``vendor/jimeng_blender_uploader/UPSTREAM.md``:

    our code enables the add-on, sets the inputs the panel would set, calls the
    add-on's operator, and projects the add-on's own state back out.

If any of these tests fail because our code grew its own validation, restoration,
or link logic, the fix is to delegate — not to weaken the test.
"""

import os
import sys
import tempfile
import types
import unittest
from unittest import mock

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
_REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
for _d in (_SCRIPTS_DIR, _REPO_ROOT):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from tests.fakes.fake_bpy import (
    FakeApp, FakeBpy, FakeCamera, FakeContext, FakeData, FakeObject,
    FakeRenderSettings, FakeScene,
)


def _install_fake_bpy(scene=None):
    """Install a fully-wired fake bpy into sys.modules and return it.

    The vendored package imports ``bpy`` at module import time and does
    ``from bpy.app.handlers import persistent``, so ``bpy`` must be a package
    with an importable ``app.handlers`` submodule. This must run before the
    vendored package is first imported.
    """
    scene = scene or _make_scene()
    fake = FakeBpy(
        data=FakeData(objects=list(scene._objects)),
        context=FakeContext(scene=scene),
        app=FakeApp(),
    )
    fake.ops = type(fake.ops)(bpy=fake)  # rebuild with the back-reference

    # bpy.app and bpy.app.handlers must be real modules for the submodule import.
    handlers_module = types.ModuleType("bpy.app.handlers")
    handlers_module.load_post = []
    handlers_module.persistent = lambda fn: fn
    app_module = types.ModuleType("bpy.app")
    app_module.handlers = handlers_module
    app_module.timers = fake.app.timers
    app_module.version_string = fake.app.version_string

    module = types.ModuleType("bpy")
    module.__path__ = []  # mark as a package so submodule imports resolve
    for attr in ("data", "context", "props", "types", "utils", "ops", "path"):
        setattr(module, attr, getattr(fake, attr))
    module.app = app_module

    sys.modules["bpy"] = module
    sys.modules["bpy.app"] = app_module
    sys.modules["bpy.app.handlers"] = handlers_module
    return fake


def _make_scene(camera_name="MainCam", frame_start=1, frame_end=44):
    cam = FakeObject(camera_name, "CAMERA", data=FakeCamera(camera_name))
    scene = FakeScene(
        frame_start=frame_start,
        frame_end=frame_end,
        render=FakeRenderSettings(engine="BLENDER_EEVEE"),
        camera=cam,
    )
    scene._objects = [cam, FakeObject("Cube", "MESH")]
    return scene


class _VendoredTestCase(unittest.TestCase):
    """Base: fresh fake bpy + fresh vendored import per test."""

    def setUp(self):
        for name in list(sys.modules):
            if name.startswith("vendor.jimeng_blender_uploader") or name == "bpy":
                del sys.modules[name]
        self.scene = _make_scene()
        self.bpy = _install_fake_bpy(self.scene)
        self.camera_render = "vendor.jimeng_blender_uploader.viewport_render.render_preview_movie"
        self.fetch_config = "vendor.jimeng_blender_uploader.dcc_config.fetch_dcc_protocol_config"
        self.start_bridge = "vendor.jimeng_blender_uploader.upload_bridge.start_local_bridge"

        # The add-on validates that referenced files really exist, so the tests
        # must hand it real paths.
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.video = os.path.join(self._tmp.name, "preview.mp4")
        with open(self.video, "wb") as f:
            f.write(b"\x00" * 2048)

    def _stub_io(self, video_path=None):
        """Stub the add-on's I/O boundaries: protocol fetch, render, bridge."""
        from vendor.jimeng_blender_uploader import dcc_config
        video_path = video_path or self.video
        config = dcc_config.fallback_config()
        patches = [
            mock.patch(self.fetch_config, return_value=config),
            mock.patch(self.camera_render, return_value=video_path),
            mock.patch(self.start_bridge, return_value={
                "redirect_url": "https://jimeng.jianying.com/ai-tool/home?channel=blender",
                "resource_info_url": "http://127.0.0.1:1234/resouce_info",
                "port": 1234,
                "video": video_path,
            }),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)


class TestDelegationToVendoredOperators(_VendoredTestCase):

    def test_camera_render_calls_the_addon_operator(self):
        from codex_bridge import run_flow
        self._stub_io()

        result = run_flow(self.bpy, {
            "flow": "camera_render",
            "camera": "MainCam",
            "resolution": "720p",
            "frameStart": 1,
            "frameEnd": 44,
            "outputDir": tempfile.mkdtemp(),
        })

        # The add-on's own operator ran, and its idname is the one we expect.
        self.assertEqual(self.bpy.last_operator[0], "jimeng.render_upload")
        self.assertEqual(result["operatorResult"], "FINISHED")

    def test_local_upload_calls_the_addon_operator(self):
        from codex_bridge import run_flow
        self._stub_io()

        result = run_flow(self.bpy, {
            "flow": "local_upload",
            "videoPath": self.video,
        })

        self.assertEqual(self.bpy.last_operator[0], "jimeng.upload_existing")
        self.assertEqual(result["operatorResult"], "FINISHED")

    def test_driver_sets_the_inputs_the_panel_would_set(self):
        from codex_bridge import run_flow
        self._stub_io()
        out_dir = tempfile.mkdtemp()

        run_flow(self.bpy, {
            "flow": "camera_render",
            "camera": "MainCam",
            "resolution": "1080p",
            "frameStart": 10,
            "frameEnd": 53,
            "outputDir": out_dir,
        })

        self.assertEqual(self.scene.jimeng_uploader_mode, "VIEWPORT")
        self.assertEqual(self.scene.jimeng_camera.name, "MainCam")
        self.assertEqual(self.scene.jimeng_resolution, "1080p")
        self.assertEqual(self.scene.jimeng_frame_start, 10)
        self.assertEqual(self.scene.jimeng_frame_end, 53)
        # The approved directory is stored resolved, so symlinked scopes cannot
        # be smuggled past the check.
        self.assertEqual(self.scene.jimeng_output_dir, os.path.realpath(out_dir))

    def test_local_upload_sets_existing_mode_and_video_path(self):
        from codex_bridge import run_flow
        self._stub_io()

        run_flow(self.bpy, {"flow": "local_upload", "videoPath": self.video})

        self.assertEqual(self.scene.jimeng_uploader_mode, "EXISTING")
        self.assertEqual(self.scene.jimeng_video_path, self.video)

    def test_register_is_called_so_operators_exist(self):
        from codex_bridge import run_flow
        self._stub_io()

        run_flow(self.bpy, {"flow": "local_upload", "videoPath": self.video})

        self.assertIn("jimeng.render_upload", self.bpy.utils.classes)
        self.assertIn("jimeng.upload_existing", self.bpy.utils.classes)


class TestAddonOwnsValidation(_VendoredTestCase):
    """Validation must come from the add-on, not from our driver."""

    def test_short_frame_range_is_rejected_by_the_addon(self):
        from codex_bridge import run_flow
        self._stub_io()

        # The add-on's protocol requires >= 44 frames; 2 must be rejected.
        result = run_flow(self.bpy, {
            "flow": "camera_render",
            "camera": "MainCam",
            "frameStart": 1,
            "frameEnd": 2,
            "outputDir": tempfile.mkdtemp(),
        })

        self.assertEqual(result["operatorResult"], "CANCELLED")
        self.assertEqual(result["jimeng_task_state"], "FAILED")
        # The add-on's own localized taxonomy reports the 44-frame minimum.
        self.assertIn("44", result["jimeng_error_message"] or "")

    def test_over_long_frame_range_is_normalized_by_the_addon(self):
        """The add-on clamps an over-long range through its own sync logic.

        We assert the add-on's normalisation ran — the frame range it hands to
        the render stays within its protocol maximum — rather than asserting an
        error, because clamping (not rejecting) is the add-on's chosen behaviour.
        """
        from codex_bridge import run_flow

        seen = {}

        def capture(scene, config):
            seen["start"] = scene.jimeng_frame_start
            seen["end"] = scene.jimeng_frame_end
            return self.video

        from vendor.jimeng_blender_uploader import dcc_config
        with mock.patch(self.fetch_config, return_value=dcc_config.fallback_config()):
            with mock.patch(self.camera_render, side_effect=capture):
                with mock.patch(self.start_bridge, return_value={
                    "redirect_url": "https://jimeng.jianying.com/ai-tool/home?channel=blender",
                    "resource_info_url": "http://127.0.0.1:1234/resouce_info",
                    "port": 1234,
                    "video": self.video,
                }):
                    run_flow(self.bpy, {
                        "flow": "camera_render",
                        "camera": "MainCam",
                        "frameStart": 1,
                        "frameEnd": 5000,
                        "outputDir": tempfile.mkdtemp(),
                    })

        self.assertIn("end", seen, "the add-on should have reached the render step")
        frame_count = seen["end"] - seen["start"] + 1
        self.assertLessEqual(frame_count, 720,
                             "the add-on must not pass an over-long range to the render")

    def test_render_failure_is_reported_through_the_addon_taxonomy(self):
        from vendor.jimeng_blender_uploader import dcc_config
        from codex_bridge import run_flow

        with mock.patch(self.fetch_config, return_value=dcc_config.fallback_config()):
            with mock.patch(self.camera_render, side_effect=RuntimeError("render exploded")):
                result = run_flow(self.bpy, {
                    "flow": "camera_render",
                    "camera": "MainCam",
                    "frameStart": 1,
                    "frameEnd": 44,
                    "outputDir": tempfile.mkdtemp(),
                })

        self.assertEqual(result["operatorResult"], "CANCELLED")
        self.assertEqual(result["jimeng_task_state"], "FAILED")
        self.assertTrue(result["jimeng_error_message"])


class TestLinkComesFromTheAddon(_VendoredTestCase):

    def test_link_is_the_addons_redirect_url(self):
        from codex_bridge import run_flow
        self._stub_io()

        result = run_flow(self.bpy, {
            "flow": "camera_render",
            "camera": "MainCam",
            "frameStart": 1,
            "frameEnd": 44,
            "outputDir": tempfile.mkdtemp(),
        })

        self.assertEqual(result["jimeng_redirect_url"],
                         "https://jimeng.jianying.com/ai-tool/home?channel=blender")
        self.assertTrue(result["jimeng_link_ready"])
        # The link reached the scene, which is how the panel would show it.
        self.assertEqual(self.scene.jimeng_redirect_url, result["jimeng_redirect_url"])

    def test_local_upload_link_is_produced_without_render(self):
        from codex_bridge import run_flow
        self._stub_io()

        with mock.patch(self.camera_render) as render:
            result = run_flow(self.bpy, {
                "flow": "local_upload",
                "videoPath": self.video,
            })
            render.assert_not_called()

        self.assertTrue(result["jimeng_redirect_url"])


class TestRequestErrors(unittest.TestCase):
    """Request-level mistakes are ours to report; they are not add-on errors."""

    def setUp(self):
        self.scene = _make_scene()
        self.bpy = _install_fake_bpy(self.scene)

    def test_unknown_flow_raises(self):
        from codex_bridge import run_flow
        with self.assertRaises(ValueError):
            run_flow(self.bpy, {"flow": "nonsense"})

    def test_local_upload_without_video_path_raises(self):
        from codex_bridge import run_flow
        with self.assertRaises(ValueError):
            run_flow(self.bpy, {"flow": "local_upload"})

    def test_unknown_camera_raises_with_the_camera_name(self):
        from codex_bridge import run_flow
        with self.assertRaises(ValueError) as ctx:
            run_flow(self.bpy, {"flow": "camera_render", "camera": "Nope"})
        self.assertIn("Nope", str(ctx.exception))

    def test_symlinked_output_dir_is_rejected(self):
        """Scope validation is ours: the add-on writes wherever it is pointed."""
        from codex_bridge import run_flow
        with tempfile.TemporaryDirectory() as td:
            real = os.path.join(td, "real")
            link = os.path.join(td, "link")
            os.makedirs(real)
            os.symlink(real, link)
            with self.assertRaises(ValueError) as ctx:
                run_flow(self.bpy, {
                    "flow": "camera_render",
                    "camera": "MainCam",
                    "outputDir": link,
                })
            self.assertIn("symlink", str(ctx.exception))

    def test_nonexistent_output_dir_is_rejected(self):
        from codex_bridge import run_flow
        with self.assertRaises(ValueError) as ctx:
            run_flow(self.bpy, {
                "flow": "camera_render",
                "camera": "MainCam",
                "outputDir": "/nonexistent/output/dir",
            })
        self.assertIn("not an existing directory", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
