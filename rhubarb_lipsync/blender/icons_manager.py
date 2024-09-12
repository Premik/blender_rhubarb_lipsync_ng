import pathlib

import bpy
import bpy.types
import bpy.utils

from rhubarb_lipsync.blender.ui_utils import resources_path


class IconsManager:
    _previews: bpy.utils.previews.ImagePreviewCollection = None
    _loaded: set[str] = set()

    @staticmethod
    def unregister() -> None:
        if IconsManager._previews:
            IconsManager._previews.close()
            # bpy.utils.previews.remove(IconsManager._previews)
            IconsManager._previews = None
            IconsManager._loaded = set()

    @staticmethod
    def get_icon(key: str) -> int:
        if IconsManager._previews is None:
            IconsManager._previews = bpy.utils.previews.new()
        prew = IconsManager._previews
        if key not in IconsManager._loaded:
            IconsManager._loaded.add(key)
            fn = key
            if not pathlib.Path(key).suffix:
                fn = f"{key}.png"  # .png default extension
            prew.load(key, str(resources_path() / fn), 'IMAGE')
        return prew[key].icon_id

    @staticmethod
    def get_image(image_name: str) -> tuple[bpy.types.Image, bpy.types.Texture]:
        """Loads an image into Blender's data blocks."""
        if not image_name.endswith(".png"):
            image_name = f"{image_name}.png"
        image_path = resources_path() / image_name
        # if not image_path.exists():
        #     raise RuntimeError(f"Image not found: {image_path}")
        img = bpy.data.images.load(str(image_path), check_existing=True)
        # img.preview_ensure()
        # Create a new texture and assign the loaded image to it
        text_name = image_name
        if text_name not in bpy.data.textures.keys():
            tex = bpy.data.textures.new(name=image_name, type='IMAGE')
            tex.extension = 'EXTEND'
            tex.image = img
        else:
            tex = bpy.data.textures[text_name]

        return img, tex

    @staticmethod
    def logo_icon() -> int:
        return IconsManager.get_icon('rhubarb64x64')
        # return IconsManager.get('1.dat')

    @staticmethod
    def placement_help_image() -> tuple[bpy.types.Image, bpy.types.Texture]:
        return IconsManager.get_image('placementSettings')
        # return IconsManager.get('1.dat')

    @staticmethod
    def cue_icon(key: str) -> int:
        return IconsManager.get_icon(f"lisa-{key}")
