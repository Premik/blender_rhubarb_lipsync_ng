## https://devtalk.blender.org/t/batch-registering-multiple-classes-in-blender-2-8/3253/8

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator, Iterator, Type, get_type_hints
import importlib
import inspect
import pkgutil
import bpy
from types import ModuleType


@dataclass
class AutoLoader:
    root: str
    modules: list[ModuleType] = field(default_factory=list)
    ordered_classes: list[Type] = field(default_factory=list)

    def __post_init__(self):
        self.collect_all_submodules()
        self.toposort_classes()

    def register(self) -> None:
        for cls in self.ordered_classes:
            bpy.utils.register_class(cls)

        for module in self.modules:
            if module.__name__ == __name__:
                continue
            if hasattr(module, "register"):
                module.register()

    def unregister(self) -> None:
        for cls in reversed(self.ordered_classes):
            bpy.utils.unregister_class(cls)

        for module in self.modules:
            if module.__name__ == __name__:
                continue
            if hasattr(module, "unregister"):
                module.unregister()

    def collect_all_submodules(self) -> None:
        directory = Path(self.root).parent
        self.modules = list(self.iter_submodules(directory, directory.name))

    def iter_submodules(self, path: Path, package_name: str) -> Iterator[ModuleType]:
        for name in sorted(self.iter_submodule_names(path)):
            yield importlib.import_module("." + name, package_name)

    def iter_submodule_names(self, path: Path, root="") -> Iterator[str]:
        for _, module_name, is_package in pkgutil.iter_modules([str(path)]):
            if is_package:
                sub_path = path / module_name
                sub_root = root + module_name + "."
                yield from self.iter_submodule_names(sub_path, sub_root)
            else:
                yield root + module_name

    def get_register_deps_dict(self) -> dict[Type, set[Type]]:
        my_classes = set(self.iter_my_classes())
        deps_dict = {}
        for cls in my_classes:
            deps_dict[cls] = set(self.iter_my_register_deps(cls, my_classes))
        return deps_dict

    def iter_my_register_deps(self, cls: Type, my_classes: set[Type]) -> Generator[Type, None, None]:
        yield from self.iter_my_deps_from_annotations(cls, my_classes)
        my_classes_by_idname = {cls.bl_idname: cls for cls in my_classes if hasattr(cls, "bl_idname")}
        yield from self.iter_my_deps_from_parent_id(cls, my_classes_by_idname)

    def iter_my_deps_from_annotations(self, cls: Type, my_classes: set[Type]) -> Generator[Type, None, None]:
        for value in get_type_hints(cls, {}, {}).values():
            dependency = self.get_dependency_from_annotation(value)
            if dependency is not None:
                if dependency in my_classes:
                    yield dependency

    def get_dependency_from_annotation(self, value: Any) -> Type:
        blender_version = bpy.app.version
        if blender_version and blender_version >= (2, 93):
            if isinstance(value, bpy.props._PropertyDeferred):
                return value.keywords.get("type")
        else:
            if isinstance(value, tuple) and len(value) == 2:
                if value[0] in (bpy.props.PointerProperty, bpy.props.CollectionProperty):
                    return value[1]["type"]
        return None

    def iter_my_deps_from_parent_id(self, cls: Type, my_classes_by_idname: dict[str, Type]) -> Generator[Type, None, None]:
        if bpy.types.Panel in cls.__bases__:
            parent_idname = getattr(cls, "bl_parent_id", None)
            if parent_idname is not None:
                parent_cls = my_classes_by_idname.get(parent_idname)
                if parent_cls is not None:
                    yield parent_cls

    def iter_my_classes(self) -> Generator[Type, None, None]:
        base_types = self.get_register_base_types()
        for cls in self.get_classes_in_modules():
            if any(base in base_types for base in cls.__bases__):
                if not getattr(cls, "is_registered", False):
                    yield cls

    def get_classes_in_modules(self) -> set[Type]:
        classes = set()
        for module in self.modules:
            for cls in self.iter_classes_in_module(module):
                classes.add(cls)
        return classes

    def iter_classes_in_module(self, module: ModuleType) -> Generator[Type, None, None]:
        for value in module.__dict__.values():
            if inspect.isclass(value):
                yield value

    def get_register_base_types(self) -> set[Type]:
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

    def toposort_classes(self) -> None:
        sorted_values = set()
        deps_dict = self.get_register_deps_dict()
        while len(deps_dict) > 0:
            unsorted = []
            for value, deps in deps_dict.items():
                if len(deps) == 0:
                    self.ordered_classes.append(value)
                    sorted_values.add(value)
                else:
                    unsorted.append(value)
            deps_dict = {value: deps_dict[value] - sorted_values for value in unsorted}
        return self.ordered_classes
