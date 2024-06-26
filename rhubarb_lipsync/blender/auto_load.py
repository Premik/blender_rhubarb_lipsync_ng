## https://devtalk.blender.org/t/batch-registering-multiple-classes-in-blender-2-8/3253/8

import importlib
import inspect
import pkgutil
from pathlib import Path
from types import ModuleType
from typing import Any, Generator, Iterator, Type, get_type_hints

import bpy

__all__ = (
    "init",
    "register",
    "unregister",
)

blender_version = bpy.app.version

modules: list[ModuleType] = []
ordered_classes: list[Type] = []


def init(root: str = __file__) -> None:
    # print(root)
    global modules
    global ordered_classes
    # print(f"{'!'*100}\n  {Path(root).parent}")

    modules = get_all_submodules(Path(root).parent)
    ordered_classes = get_ordered_classes_to_register(modules)


def register() -> None:
    for cls in ordered_classes:
        # print(f"Registering class {cls}")
        bpy.utils.register_class(cls)

    for module in modules:
        if module.__name__ == __name__:
            continue
        if hasattr(module, "register"):
            # print(f"Registering {module}")
            module.register()


def unregister() -> None:
    for cls in reversed(ordered_classes):
        bpy.utils.unregister_class(cls)

    for module in modules:
        if module.__name__ == __name__:
            continue
        if hasattr(module, "unregister"):
            module.unregister()


# Import modules
#################################################


def get_all_submodules(directory: Path) -> list[ModuleType]:
    return list(iter_submodules(directory, directory.name))


def iter_submodules(path: Path, package_name: str) -> Iterator[ModuleType]:
    for name in sorted(iter_submodule_names(path)):
        # print(f"Importing: {name}@{package_name}")
        yield importlib.import_module("." + name, package_name)


def iter_submodule_names(path: Path, root="") -> Iterator[str]:
    # print(f"{'!'*100}\n  {path}")
    # for m in pkgutil.iter_modules(): print(m)
    for _, module_name, is_package in pkgutil.iter_modules([str(path)]):
        # print(f"{'!'*100}\n  {module_name}")
        if is_package:
            sub_path = path / module_name
            sub_root = root + module_name + "."
            yield from iter_submodule_names(sub_path, sub_root)
        else:
            yield root + module_name


# Find classes to register
#################################################


def get_ordered_classes_to_register(modules: list[ModuleType]) -> list[Type]:
    return toposort(get_register_deps_dict(modules))


def get_register_deps_dict(modules: list[ModuleType]) -> dict[Type, set[Type]]:
    my_classes = set(iter_my_classes(modules))
    deps_dict = {}
    for cls in my_classes:
        deps_dict[cls] = set(iter_my_register_deps(cls, my_classes))
    return deps_dict


def iter_my_register_deps(cls: Type, my_classes: set[Type]) -> Generator[Type, None, None]:
    yield from iter_my_deps_from_annotations(cls, my_classes)
    my_classes_by_idname = {cls.bl_idname: cls for cls in my_classes if hasattr(cls, "bl_idname")}
    yield from iter_my_deps_from_parent_id(cls, my_classes_by_idname)


def iter_my_deps_from_annotations(cls: Type, my_classes: set[Type]) -> Generator[Type, None, None]:
    for value in get_type_hints(cls, {}, {}).values():
        dependency = get_dependency_from_annotation(value)
        if dependency is not None:
            if dependency in my_classes:
                yield dependency


def get_dependency_from_annotation(value: Any) -> Type:
    if blender_version and blender_version >= (2, 93):
        if isinstance(value, bpy.props._PropertyDeferred):
            return value.keywords.get("type")
    else:
        if isinstance(value, tuple) and len(value) == 2:
            if value[0] in (bpy.props.PointerProperty, bpy.props.CollectionProperty):
                return value[1]["type"]
    return None


def iter_my_deps_from_parent_id(cls: Type, my_classes_by_idname: dict[str, Type]) -> Generator[Type, None, None]:
    if bpy.types.Panel in cls.__bases__:
        parent_idname = getattr(cls, "bl_parent_id", None)
        if parent_idname is not None:
            parent_cls = my_classes_by_idname.get(parent_idname)
            if parent_cls is not None:
                yield parent_cls


def iter_my_classes(modules: list[ModuleType]) -> Generator[Type, None, None]:
    base_types = get_register_base_types()
    for cls in get_classes_in_modules(modules):
        if any(base in base_types for base in cls.__bases__):
            if not getattr(cls, "is_registered", False):
                yield cls


def get_classes_in_modules(modules: list[ModuleType]) -> set[Type]:
    classes = set()
    for module in modules:
        for cls in iter_classes_in_module(module):
            classes.add(cls)
    return classes


def iter_classes_in_module(module: ModuleType) -> Generator[Type, None, None]:
    for value in module.__dict__.values():
        if inspect.isclass(value):
            yield value


def get_register_base_types() -> set[Type]:
    return set(
        getattr(bpy.types, name)
        for name in [
            "Panel",
            "Operator",
            "PropertyGroup",
            "AddonPreferences",
            "Header",
            "Menu",
            "Node",
            "NodeSocket",
            "NodeTree",
            "UIList",
            "RenderEngine",
            "Gizmo",
            "GizmoGroup",
        ]
    )


# Find order to register to solve dependencies
#################################################


def toposort(deps_dict: dict[Type, set[Type]]) -> list[Type]:
    sorted_list = []
    sorted_values = set()
    while len(deps_dict) > 0:
        unsorted = []
        for value, deps in deps_dict.items():
            if len(deps) == 0:
                sorted_list.append(value)
                sorted_values.add(value)
            else:
                unsorted.append(value)
        deps_dict = {value: deps_dict[value] - sorted_values for value in unsorted}
    return sorted_list
