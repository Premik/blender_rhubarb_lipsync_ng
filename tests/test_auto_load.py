import unittest

import bpy

from rhubarb_lipsync.blender.auto_load import AutoLoader


class RegisteredProps(bpy.types.PropertyGroup):
    bl_idname = 'rlps_test_registered_props'


class UnregisteredProps(bpy.types.PropertyGroup):
    bl_idname = 'rlps_test_unregistered_props'


class AutoLoaderUnregisterTest(unittest.TestCase):
    """unregister() must tolerate classes that never got registered, e.g. after a partially failed register()."""

    def make_loader(self, ordered_classes: list) -> AutoLoader:
        loader = AutoLoader(root_init_file=__file__, root_package_name='rlps_test')
        loader.ordered_classes = ordered_classes
        loader.modules = []
        return loader

    def cleanup_class(self, cls: type) -> None:
        if getattr(cls, 'is_registered', False):
            bpy.utils.unregister_class(cls)

    def test_unregister_skips_unregistered_classes(self) -> None:
        bpy.utils.register_class(RegisteredProps)
        self.addCleanup(self.cleanup_class, RegisteredProps)

        # Must not raise, although UnregisteredProps was never registered
        self.make_loader([UnregisteredProps, RegisteredProps]).unregister()

        assert not getattr(RegisteredProps, 'is_registered', False)  # The registered one is unregistered
        assert not getattr(UnregisteredProps, 'is_registered', False)

    def test_unregister_with_no_registered_classes(self) -> None:
        self.make_loader([UnregisteredProps]).unregister()  # Must not raise


if __name__ == '__main__':
    unittest.main()
