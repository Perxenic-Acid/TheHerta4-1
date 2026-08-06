"""Registration module for the Material Combiner addon.

This module handles the registration and unregistration of all Blender classes
used by the addon. It also manages version-specific property annotations.
"""

import bpy

from . import (
    extend_lists,
    extend_types,
    globs,
    operators,
    ui,
)
from .type_annotations import BlClasses

__bl_classes = [
    ui.selection_menu.SMC_MT_SelectionMenu,
    ui.main_panel.MaterialCombinerPanel,
    ui.property_panel.PropertyMenu,
    operators.combine_list.MaterialListRefreshOperator,
    operators.combine_list.MaterialListToggleOperator,
    operators.combine_list.SelectAllMaterials,
    operators.combine_list.SelectNoneMaterials,
    operators.combiner.Combiner,
    operators.get_pillow.InstallPIL,
    operators.get_pillow.CheckPillow,
    extend_types.CombineListEntry,
    extend_lists.SMC_UL_Combine_List,
]


def register_all() -> None:
    """Register all components of the addon.

    Registers all classes and properties used by the material combiner.
    Called from the main TheHerta4 plugin's register().
    """
    _register_classes()
    extend_types.register()


def unregister_all() -> None:
    """Unregister all components of the addon.

    Unregisters all classes and properties used by the material combiner.
    Called from the main TheHerta4 plugin's unregister().
    """
    _unregister_classes()
    extend_types.unregister()


def _register_classes() -> None:
    """Register all Blender classes used by the addon.

    Converts properties to annotations as needed and logs registration results.
    """
    count = 0
    for cls in __bl_classes:
        make_annotations(cls)
        try:
            bpy.utils.register_class(cls)
            count += 1
        except ValueError as e:
            print("Error:", cls, e)
    print("Registered", count, "Material Combiner classes.")
    if count < len(__bl_classes):
        print(
            "Skipped", len(__bl_classes) - count, "Material Combiner classes."
        )


def _unregister_classes() -> None:
    """Unregister all Blender classes used by the addon.

    Classes are unregistered in reverse order to handle dependencies.
    """
    count = 0
    for cls in reversed(__bl_classes):
        try:
            bpy.utils.unregister_class(cls)
            count += 1
        except (ValueError, RuntimeError) as e:
            print("Error:", cls, e)
    print("Unregistered", count, "Material Combiner classes.")


def make_annotations(cls: BlClasses) -> BlClasses:
    """Convert class properties to annotations for Blender 2.80+.

    This function handles the transition from Blender's old property
    definition system to the new annotation-based system.

    Args:
        cls: Blender class to process.

    Returns:
        The processed class with properties converted to annotations.
    """
    bl_props = {
        k: v
        for k, v in cls.__dict__.items()
        if isinstance(v, bpy.props._PropertyDeferred)
    }

    if bl_props:
        if "__annotations__" not in cls.__dict__:
            cls.__annotations__ = {}

        annotations = cls.__dict__["__annotations__"]

        for k, v in bl_props.items():
            annotations[k] = v
            delattr(cls, k)

    return cls
