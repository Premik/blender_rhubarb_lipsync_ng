import unittest


def has_blender_audacity_support() -> bool:
    """Official bpy from pip for some reason comes without `aud` module and blender fails to work with Sound objects"""
    try:
        import aud

        return getattr(aud, 'MOCK', False)
    except ImportError:
        return False  # handle the


def skip_no_aud(test_func):
    return unittest.skipIf(has_blender_audacity_support(), "No AUD support, has to skip")(test_func)
