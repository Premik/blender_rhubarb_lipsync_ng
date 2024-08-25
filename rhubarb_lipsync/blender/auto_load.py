## https://devtalk.blender.org/t/batch-registering-multiple-classes-in-blender-2-8/3253/8

import importlib
import inspect
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Generator, Iterable, Iterator, Type, get_type_hints

import bpy


@dataclass
class AutoLoader:
    root_init_file: str
    root_package_name: str
    modules: list[ModuleType] = field(default_factory=list)
    ordered_classes: list[Type] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)

    def trace_pop(self) -> str:
        return self.trace.pop()

    def trace_push(self, v: str = "") -> None:
        self.trace.append(v)

    @property
    def trace_peek(self) -> str:
        return self.trace[-1]

    @trace_peek.setter
    def trace_peek(self, value: str) -> None:
        self.trace[-1] = value

    def trace_items(self, items: Iterable, frame_name: str) -> Generator:
        self.trace_push(frame_name)
        for item in items:
            self.trace_push(str(item))  # Push only the first item
            yield item
            self.trace_peek = str(item)  # Modify the last pushed item to be `str(item)`
            self.trace_pop()  # Pop the last item

        self.trace_pop()  # Pop the frame name

    def trace_str(self) -> str:
        """Joins the trace list into a formatted string: frame:item/frame:item/..."""
        pairs = [f"{self.trace[i]}={self.trace[i + 1]}" for i in range(0, len(self.trace), 2)]
        return "/".join(pairs)

    def trace_print_str(self) -> str:
        if self.trace:
            print('-' * 80)
            print(f"- {self.trace_str()}")
            print('-' * 80)

    def find_classes(self) -> None:
        self.collect_all_submodules()
        self.toposort_classes()

    def register(self) -> None:
        for cls in self.trace_items(self.ordered_classes, "class"):
            bpy.utils.register_class(cls)

        for module in self.trace_items(self.modules, "module"):
            if module.__name__ == __name__:
                continue
            if hasattr(module, "register"):
                module.register()

    def unregister(self) -> None:
        for cls in self.trace_items(reversed(self.ordered_classes), "class"):
            bpy.utils.unregister_class(cls)

        for module in self.trace_items(self.modules, "module"):
            if module.__name__ == __name__:
                continue
            if hasattr(module, "unregister"):
                module.unregister()

    def collect_all_submodules(self) -> None:
        directory = Path(self.root_init_file).parent
        self.modules = list(self.iter_submodules(directory, self.root_package_name))

    def iter_submodules(self, path: Path, package_name: str) -> Iterator[ModuleType]:
        for name in self.trace_items(sorted(self.iter_submodule_names(path)), f"package={package_name},module"):
            yield importlib.import_module("." + name, package_name)

    def iter_submodule_names(self, path: Path, root="") -> Iterator[str]:
        for _, module_name, is_package in self.trace_items(pkgutil.iter_modules([str(path)]), f"path:{path} module_details"):
            if is_package:
                sub_path = path / module_name
                sub_root = root + module_name + "."
                yield from self.iter_submodule_names(sub_path, sub_root)
            else:
                yield root + module_name

    def get_register_deps_dict(self) -> dict[Type, set[Type]]:
        my_classes = set(self.iter_my_classes())
        deps_dict = {}
        for cls in self.trace_items(my_classes, "class"):
            deps_dict[cls] = set(self.iter_my_register_deps(cls, my_classes))
        return deps_dict

    def iter_my_register_deps(self, cls: Type, my_classes: set[Type]) -> Generator[Type, None, None]:
        yield from self.iter_my_deps_from_annotations(cls, my_classes)
        my_classes_by_idname = {cls.bl_idname: cls for cls in my_classes if hasattr(cls, "bl_idname")}
        yield from self.iter_my_deps_from_parent_id(cls, my_classes_by_idname)

    def iter_my_deps_from_annotations(self, cls: Type, my_classes: set[Type]) -> Generator[Type, None, None]:
        for value in self.trace_items(get_type_hints(cls, {}, {}).values(), f"class={cls} obj"):
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
        for cls in self.trace_items(self.get_classes_in_modules(), "module"):
            if any(base in base_types for base in cls.__bases__):
                if not getattr(cls, "is_registered", False):
                    yield cls

    def get_classes_in_modules(self) -> set[Type]:
        classes = set()
        for module in self.trace_items(self.modules, "module"):
            for cls in self.trace_items(self.iter_classes_in_module(module), "class"):
                classes.add(cls)
        return classes

    def iter_classes_in_module(self, module: ModuleType) -> Generator[Type, None, None]:
        for value in self.trace_items(module.__dict__.values(), "attr"):
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
