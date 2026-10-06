import bpy

# FastFX
# File: __init__.py
# The file that ties everything together.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

bl_info = {
    "name": "FastFX",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "File > Import-Export , 3DView",
    "description": "Import/Export shapes and collision box data for Star Fox 1/2/EX.",
    "author": "Sunlit",
    "category": "Import-Export",
}

from .fmt_3dan import Export3DAN
from .fmt_3dg1 import Export3DG1, Import3DGI
from .fmt_asm import ExportAnimatedToASM, ExportToBSP, ExportToBSPTreeless, ExportToGZS, ImportBSPOperator
from .colboxes import (
    OBJECT_OT_export_colboxes,
    OBJECT_OT_generate_colbox,
    OBJECT_OT_import_colboxes_clipboard,
    OBJECT_OT_update_colboxes,
    OBJECT_OT_update_colbox_offsets,
)
from .common import VertexOperation
from .menus import TOPBAR_MT_fastfx_asm, TOPBAR_MT_fastfx_asm_animated, menu_func_export, menu_func_import
from .superfx import OBJECT_OT_create_super_fx
from .ui import (
    AddShapeHeaderPropertiesOperator,
    OBJECT_OT_add_2_point_face,
    OBJECT_OT_assign_edge_material,
    OBJECT_OT_apply_material_colors,
    OBJECT_OT_apply_material_colors_simple,
    OBJECT_OT_select_twisted_faces,
    OBJECT_OT_toggle_backface_culling,
    VIEW3D_PT_fastfx_tools,
    register_edge_material_overlay,
    register_edge_material_overlay_settings,
    unregister_edge_material_overlay,
    unregister_edge_material_overlay_settings,
)


# =========================
# Registration
# =========================
classes = (
    Import3DGI,
    Export3DG1,
    VertexOperation,
    OBJECT_OT_toggle_backface_culling,
    OBJECT_OT_add_2_point_face,
    OBJECT_OT_assign_edge_material,
    OBJECT_OT_apply_material_colors,
    OBJECT_OT_apply_material_colors_simple,
    OBJECT_OT_select_twisted_faces,
    VIEW3D_PT_fastfx_tools,
    OBJECT_OT_create_super_fx,
    OBJECT_OT_import_colboxes_clipboard,
    OBJECT_OT_export_colboxes,
    OBJECT_OT_update_colboxes,
    OBJECT_OT_update_colbox_offsets,
    OBJECT_OT_generate_colbox,
    ImportBSPOperator,
    Export3DAN,
    ExportToBSP,
    ExportToBSPTreeless,
    ExportToGZS,
    ExportAnimatedToASM,
    TOPBAR_MT_fastfx_asm,
    TOPBAR_MT_fastfx_asm_animated,
    AddShapeHeaderPropertiesOperator,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    register_edge_material_overlay_settings()
    register_edge_material_overlay()


def unregister():
    unregister_edge_material_overlay()
    unregister_edge_material_overlay_settings()
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
