import sys

# https://devtalk.blender.org/t/plugin-hot-reload-by-cleaning-sys-modules/20040/4


def cleanse_modules(prefix=__name__):
    """search for your plugin modules in blender python sys.modules and remove them"""

    for module_name in sorted(sys.modules.keys()):
        if module_name.startswith(prefix):
            del sys.modules[module_name]


import importlib

m = importlib.import_module("rhubarb_lipsync")
m.unregister()
importlib.reload(m)
m.register()

print('rhubarb_lipsync' in locals())
print("*" * 100)
