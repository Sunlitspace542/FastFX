# FastFX
# File: ui.py
# FastFX menu panel functions.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

import bpy
import bmesh
import blf
import gpu
import math
import os
import re
import tempfile
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils.kdtree import KDTree

from .common import (
    VertexOperation,
    convert_two_point_faces_to_edges,
    hex_to_rgb,
    is_mesh_animated,
)
from .animation import animation_frame_count, is_vertex_animation
from .fmt_3dg1 import EDGE_COLOR_ATTRIBUTE, read_3dg1
from .palette import id_0_c_components_rgb, id_0_c_rgb
from .slopes import selected_slope_settings, slope_face_labels
from .superfx import super_fx_node_group, super_fx_static_dither_node_group
from .textures import (
    OBJECT_OT_apply_texture_material,
    OBJECT_OT_create_texture_material,
    OBJECT_OT_load_texture_image,
    is_texture_material,
)

# =========================
# FastFX Menu Panel/UI - Edge Material Overlay
# =========================

_edge_material_overlay_handle = None
_edge_material_line_overlay_handle = None

_SUPER_FX_BASE_DITHER = 96.18470001220703
_SUPER_FX_PIXELS_PER_ASPECT_UNIT = 32.0
_SUPER_FX_INPUT_NAMES = ("Aspect X", "Aspect Y", "Dither")


def _super_fx_nodes(material):
    if not material or not material.use_nodes or not material.node_tree:
        return []
    return [
        node for node in material.node_tree.nodes
        if node.bl_idname == "ShaderNodeGroup"
        and node.node_tree
        and (
            node.node_tree.name == "Super FX"
            or node.node_tree.get("fastfx_static_dither")
        )
    ]


def _is_solid_dither_palette(settings):
    colors = tuple(settings.get(f"Colour {index}") for index in range(1, 5))
    return (
        all(color is not None for color in colors)
        and colors[0] == colors[1]
        and colors[2] == colors[3]
        and colors[0] != colors[2]
    )


def _palette_material_name(material):
    return re.sub(r"\.\d{3}$", "", material.name)


def _material_uses_solid_dither_palette(material):
    if not material:
        return False
    material_name = _palette_material_name(material)
    if not (material_name.startswith("FX") or material_name.startswith("FE")):
        return False
    color_index_text = material_name[2:]
    if not color_index_text.isdigit():
        return False
    settings = id_0_c_components_rgb.get(int(color_index_text), {})
    return _is_solid_dither_palette(settings)


def _apply_super_fx_settings_to_all(settings):
    updated_materials = 0
    for material in bpy.data.materials:
        material_updated = False
        for node in _super_fx_nodes(material):
            if all(input_name in node.inputs for input_name in settings):
                for input_name, value in settings.items():
                    node.inputs[input_name].default_value = value
                material_updated = True
        if material_updated:
            updated_materials += 1
    return updated_materials


def _update_preset_shapehdr(scene, context):
    if scene.fastfx_game_preset == "STARFOX2":
        scene.fastfx_export_simplified_shapehdr = False
    elif scene.fastfx_game_preset == "STARFOXEX":
        scene.fastfx_export_simplified_shapehdr = True


def register_edge_material_overlay_settings():
    bpy.types.Scene.fastfx_game_preset = bpy.props.EnumProperty(
        name="Game Preset",
        description="Choose which game's editing features to show",
        items=[
            ("STARFOX", "Star Fox", "Hide Star Fox 2 slope tools and labels"),
            ("STARFOX2", "Star Fox 2", "Show Star Fox 2 slope tools and labels"),
            ("STARFOXEX", "Star Fox EX", "Force simplified ASM ShapeHdr output"),
        ],
        default="STARFOX",
        update=_update_preset_shapehdr,
    )
    bpy.types.Scene.fastfx_show_edge_material_labels = bpy.props.BoolProperty(
        name="Show Material Labels",
        description="Show FX material names over assigned edges and 2-point faces",
        default=True,
    )
    bpy.types.Scene.fastfx_show_edge_material_lines = bpy.props.BoolProperty(
        name="Show Colored Edge Lines",
        description="Draw palette-colored lines over assigned edges and 2-point faces",
        default=True,
    )


def unregister_edge_material_overlay_settings():
    del bpy.types.Scene.fastfx_game_preset
    del bpy.types.Scene.fastfx_show_edge_material_labels
    del bpy.types.Scene.fastfx_show_edge_material_lines


def register_export_options_settings():
    bpy.types.Scene.fastfx_export_sort_mode = bpy.props.EnumProperty(
        name="Sort Mode",
        description="Choose how to sort faces and edges in exported models",
        items=[
            ("distance", "Distance from Origin", "Sort by distance from the origin"),
            ("material", "Material Order", "Sort by material order; last material is drawn first"),
            ("none", "No Sorting", "Keep Blender's internal face and edge order"),
        ],
        default="distance",
    )
    bpy.types.Scene.fastfx_export_compress_point_pairs = bpy.props.BoolProperty(
        name="Compress Point Pairs",
        description="Group exact X-mirrored vertex pairs together for compact encoding",
        default=True,
    )
    bpy.types.Scene.fastfx_export_simplified_shapehdr = bpy.props.BoolProperty(
        name="Simplified ShapeHdr (ASM)",
        description="Exclude LODs from the ASM shape header",
        default=False,
    )


def unregister_export_options_settings():
    del bpy.types.Scene.fastfx_export_sort_mode
    del bpy.types.Scene.fastfx_export_compress_point_pairs
    del bpy.types.Scene.fastfx_export_simplified_shapehdr


def register_import_options_settings():
    bpy.types.Scene.fastfx_import_convert_two_point_faces = bpy.props.BoolProperty(
        name="Convert 2-Gons to Edges",
        description="Import 2-point faces as tagged loose edges when the object is static",
        default=False,
    )


def unregister_import_options_settings():
    del bpy.types.Scene.fastfx_import_convert_two_point_faces


def _edge_material_label(material):
    if material is None:
        return None
    name = re.sub(r"\.\d{3}$", "", material.name)
    return name if name.startswith("FX") else None


def _edge_material_segments(context, obj):
    edge_labels = []
    if context.mode == 'EDIT_MESH' and obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(obj.data)
        layer = bm.edges.layers.int.get(EDGE_COLOR_ATTRIBUTE)
        if layer is not None:
            for edge in bm.edges:
                color_index = edge[layer]
                if color_index >= 0 and not edge.link_faces:
                    edge_labels.append((edge.verts[0].co, edge.verts[1].co, f"FX{color_index}"))

        for face in bm.faces:
            if len(face.verts) != 2:
                continue
            material_index = face.material_index
            if material_index < len(obj.material_slots):
                label = _edge_material_label(obj.material_slots[material_index].material)
                if label:
                    edge_labels.append((face.verts[0].co, face.verts[1].co, label))
    else:
        mesh = obj.data
        vertices = mesh.vertices
        if is_vertex_animation(obj):
            evaluated_obj = obj.evaluated_get(context.evaluated_depsgraph_get())
            vertices = evaluated_obj.data.vertices
        edge_color_attribute = mesh.attributes.get(EDGE_COLOR_ATTRIBUTE)
        if (
            edge_color_attribute is not None
            and edge_color_attribute.domain == 'EDGE'
            and edge_color_attribute.data_type == 'INT'
        ):
            face_edge_keys = {
                tuple(sorted(edge_key))
                for poly in mesh.polygons
                for edge_key in poly.edge_keys
            }
            for edge, color_value in zip(mesh.edges, edge_color_attribute.data):
                edge_key = tuple(sorted(edge.vertices))
                if color_value.value >= 0 and edge_key not in face_edge_keys:
                    v1, v2 = edge.vertices
                    edge_labels.append((
                        vertices[v1].co.copy(),
                        vertices[v2].co.copy(),
                        f"FX{color_value.value}",
                    ))

        for poly in mesh.polygons:
            if len(poly.vertices) != 2 or poly.material_index >= len(obj.material_slots):
                continue
            label = _edge_material_label(obj.material_slots[poly.material_index].material)
            if label:
                v1, v2 = poly.vertices
                edge_labels.append((
                    vertices[v1].co.copy(),
                    vertices[v2].co.copy(),
                    label,
                ))

    return edge_labels


def _draw_edge_material_lines():
    context = bpy.context
    if not context.scene.fastfx_show_edge_material_lines:
        return

    obj = context.active_object
    if (
        context.area is None
        or context.area.type != 'VIEW_3D'
        or context.region is None
        or context.region.type != 'WINDOW'
        or context.region_data is None
        or obj is None
        or obj.type != 'MESH'
    ):
        return

    segments = _edge_material_segments(context, obj)
    if not segments:
        return

    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
    gpu.state.depth_test_set('LESS_EQUAL')
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(3.0)
    try:
        shader.bind()
        for start, end, label in segments:
            color_index = int(label[2:]) if label[2:].isdigit() else 0
            color = hex_to_rgb(id_0_c_rgb.get(color_index, "#FFFFFF"))
            batch = batch_for_shader(
                shader,
                'LINES',
                {
                    "pos": (
                        (obj.matrix_world @ start)[:],
                        (obj.matrix_world @ end)[:],
                    )
                },
            )
            shader.uniform_float("color", color)
            batch.draw(shader)
    finally:
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')
        gpu.state.depth_test_set('NONE')


def _draw_edge_material_labels():
    context = bpy.context
    show_edge_labels = context.scene.fastfx_show_edge_material_labels
    show_slope_labels = (
        context.scene.fastfx_game_preset == "STARFOX2"
        and context.scene.fastfx_show_slope_labels
    )
    if not show_edge_labels and not show_slope_labels:
        return

    obj = context.active_object
    region = context.region
    region_3d = context.region_data
    if (
        context.area is None
        or context.area.type != 'VIEW_3D'
        or region is None
        or region.type != 'WINDOW'
        or region_3d is None
        or obj is None
        or obj.type != 'MESH'
    ):
        return

    projected_labels = []
    if show_edge_labels:
        for start, end, label in _edge_material_segments(context, obj):
            start_2d = view3d_utils.location_3d_to_region_2d(
                region, region_3d, obj.matrix_world @ start
            )
            end_2d = view3d_utils.location_3d_to_region_2d(
                region, region_3d, obj.matrix_world @ end
            )
            if start_2d is None or end_2d is None:
                continue

            color_index = int(label[2:]) if label[2:].isdigit() else 0
            color = hex_to_rgb(id_0_c_rgb.get(color_index, "#FFFFFF"))
            midpoint = (start_2d + end_2d) / 2
            projected_labels.append((midpoint, label, color, 4))

    if show_slope_labels:
        slope_colors = {
            "GROUND": "#62D66B",
            "WATER": "#55AFFF",
            "ICE": "#75E5FF",
            "GRASS": "#B8E65C",
        }
        for center, label in slope_face_labels(context, obj):
            position = view3d_utils.location_3d_to_region_2d(
                region, region_3d, obj.matrix_world @ center
            )
            if position is None:
                continue
            color = hex_to_rgb(slope_colors.get(label, "#E6A0FF"))
            projected_labels.append((position, label, color, 0))

    if projected_labels:
        font_id = 0
        if bpy.app.version >= (4, 0, 0):
            blf.size(font_id, 12)
        else:
            blf.size(font_id, 12, 72)
        blf.enable(font_id, blf.SHADOW)
        blf.shadow(font_id, 3, 0.0, 0.0, 0.0, 1.0)
        blf.shadow_offset(font_id, 1, -1)
        for position, label, color, vertical_offset in projected_labels:
            text_width, _ = blf.dimensions(font_id, label)
            blf.position(
                font_id,
                position.x - text_width / 2,
                position.y + vertical_offset,
                0,
            )
            blf.color(font_id, *color)
            blf.draw(font_id, label)
        blf.disable(font_id, blf.SHADOW)


def register_edge_material_overlay():
    global _edge_material_overlay_handle, _edge_material_line_overlay_handle
    if _edge_material_overlay_handle is None:
        _edge_material_overlay_handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_edge_material_labels, (), 'WINDOW', 'POST_PIXEL'
        )
    if _edge_material_line_overlay_handle is None:
        _edge_material_line_overlay_handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_edge_material_lines, (), 'WINDOW', 'POST_VIEW'
        )


def unregister_edge_material_overlay():
    global _edge_material_overlay_handle, _edge_material_line_overlay_handle
    if _edge_material_overlay_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_edge_material_overlay_handle, 'WINDOW')
        _edge_material_overlay_handle = None
    if _edge_material_line_overlay_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_edge_material_line_overlay_handle, 'WINDOW')
        _edge_material_line_overlay_handle = None


# =========================
# FastFX Menu Panel -  Palette assignment (fancy)
# =========================
class OBJECT_OT_create_material_range(bpy.types.Operator):
    """Create and assign a range of FX# materials"""
    bl_idname = "object.create_material_range"
    bl_label = "Create FX Material Range"
    bl_options = {'REGISTER', 'UNDO'}

    start_index: bpy.props.IntProperty(
        name="From FX",
        description="First material index to create",
        min=0,
        max=255,
        default=0,
    )
    end_index: bpy.props.IntProperty(
        name="To FX",
        description="Last material index to create",
        min=0,
        max=255,
        default=max(id_0_c_rgb),
    )

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.object.type == "MESH"
            and context.object.mode == "OBJECT"
        )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.start_index > self.end_index:
            self.report({'ERROR'}, "The first FX# index must not exceed the last FX# index.")
            return {'CANCELLED'}

        obj = context.object
        first_material_index = None
        created_count = 0
        for color_index in range(self.start_index, self.end_index + 1):
            material_name = f"FX{color_index}"
            material = bpy.data.materials.get(material_name)
            if material is None:
                material = bpy.data.materials.new(name=material_name)
                created_count += 1

            material_index = next(
                (
                    index for index, slot_material in enumerate(obj.data.materials)
                    if slot_material == material
                ),
                None,
            )
            if material_index is None:
                obj.data.materials.append(material)
                material_index = len(obj.data.materials) - 1
            if first_material_index is None:
                first_material_index = material_index

        if first_material_index is None:
            self.report({'ERROR'}, "No FX# materials were prepared.")
            return {'CANCELLED'}
        obj.active_material_index = first_material_index
        self.report(
            {'INFO'},
            f"Prepared FX{self.start_index}-FX{self.end_index} "
            f"({created_count} new materials)",
        )
        return {'FINISHED'}


class OBJECT_OT_apply_material_colors(bpy.types.Operator):
    """Apply colors and additional settings based on material names (FX#)"""
    bl_idname = "object.apply_material_colors"
    bl_label = "Apply Material Palette (Fancy)"

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "No mesh object selected")
            return {'CANCELLED'}

        if not obj.data.materials:
            self.report({'WARNING'}, "No materials found on selected object")
            return {'CANCELLED'}

        # Ensure the Super FX node group exists
        if "Super FX" not in bpy.data.node_groups:
            self.report({'WARNING'}, "No Super FX node group")
            return {'CANCELLED'}

        static_dither_group = None
        if any(
            _material_uses_solid_dither_palette(material_slot.material)
            for material_slot in obj.material_slots
        ):
            try:
                static_dither_group = super_fx_static_dither_node_group()
            except RuntimeError as error:
                self.report({'ERROR'}, str(error))
                return {'CANCELLED'}

        for material_slot in obj.material_slots:
            material = material_slot.material
            if material:
                material_name = _palette_material_name(material)
                if not (material_name.startswith("FX") or material_name.startswith("FE")):
                    continue
                try:
                    # Extract color index from the material name
                    color_index = int(material_name[2:])
                    settings = id_0_c_components_rgb.get(color_index)

                    if not settings:
                        self.report({'WARNING'}, f"No settings found for material '{material.name}'")
                        continue

                    # Ensure the material uses nodes
                    material.use_nodes = True

                    # Clear existing nodes
                    node_tree = material.node_tree
                    nodes = node_tree.nodes
                    links = node_tree.links
                    nodes.clear()

                    # Create material output node and Super FX node
                    output_node = nodes.new(type="ShaderNodeOutputMaterial")
                    output_node.location = (300, 0)

                    super_fx = nodes.new(type="ShaderNodeGroup")
                    super_fx.node_tree = (
                        static_dither_group
                        if _is_solid_dither_palette(settings)
                        else bpy.data.node_groups["Super FX"]
                    )
                    super_fx.location = (0, 0)

                    # Link Super FX to material output
                    links.new(super_fx.outputs["Emission"], output_node.inputs["Surface"])

                    # Assign colors to the Super FX node group inputs
                    for input_name, value in settings.items():
                        if input_name.startswith("Colour"):
                            # Process color inputs
                            if input_name in super_fx.inputs:
                                super_fx.inputs[input_name].default_value = hex_to_rgb(value)
                        if input_name.startswith("Dither"):
                            # Process dither inputs
                            if input_name in super_fx.inputs:
                                super_fx.inputs[input_name].default_value = float(value)
                        else:
                            # Handle other material settings
                            if input_name == "Carry Over":
                                try:
                                    super_fx.inputs[input_name].default_value = float(value)
                                except ValueError:
                                    self.report({'WARNING'}, f"Invalid value for '{input_name}' in material '{material.name}'")

                    # Set viewport color
                    hex_color = id_0_c_rgb.get(color_index, "#FFFFFF")  # Default to white if not defined
                    linear_rgb_color = hex_to_rgb(hex_color)
                    material.diffuse_color = linear_rgb_color

                except ValueError:
                    self.report({'WARNING'}, f"Material '{material.name}' has invalid FX# or FE# format")
                    continue

        self.report({'INFO'}, "Palette applied to materials")
        return {'FINISHED'}


class OBJECT_OT_apply_super_fx_settings_to_all(bpy.types.Operator):
    """Copy the active material's Super FX settings to all Super FX materials"""
    bl_idname = "object.apply_super_fx_settings_to_all"
    bl_label = "Apply Settings to All Materials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        source_material = context.object.active_material if context.object else None
        source_nodes = _super_fx_nodes(source_material)
        if not source_nodes:
            self.report({'WARNING'}, "Active material has no Super FX node")
            return {'CANCELLED'}

        source_node = source_nodes[0]
        if any(input_name not in source_node.inputs for input_name in _SUPER_FX_INPUT_NAMES):
            self.report({'ERROR'}, "Active material's Super FX node is missing settings")
            return {'CANCELLED'}
        values = {
            input_name: source_node.inputs[input_name].default_value
            for input_name in _SUPER_FX_INPUT_NAMES
        }
        updated_materials = _apply_super_fx_settings_to_all(values)
        if not updated_materials:
            self.report({'WARNING'}, "No compatible Super FX materials found")
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Applied Super FX settings to {updated_materials} materials",
        )
        return {'FINISHED'}


class OBJECT_OT_calculate_super_fx_settings(bpy.types.Operator):
    """Calculate Super FX settings from the current 3D viewport dimensions"""
    bl_idname = "object.calculate_super_fx_settings"
    bl_label = "Calculate for Viewport (All Materials)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        area = context.area
        if area is None or area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run this from a 3D View")
            return {'CANCELLED'}

        viewport_region = next(
            (region for region in area.regions if region.type == 'WINDOW'),
            None,
        )
        if viewport_region is None or viewport_region.width <= 0 or viewport_region.height <= 0:
            self.report({'WARNING'}, "The 3D viewport has no usable dimensions")
            return {'CANCELLED'}

        aspect_scale = max(
            _SUPER_FX_PIXELS_PER_ASPECT_UNIT,
            viewport_region.width / 100.0,
            viewport_region.height / 100.0,
        )
        settings = {
            "Aspect X": max(
                1.0,
                min(viewport_region.width / aspect_scale, 100.0),
            ),
            "Aspect Y": max(
                1.0,
                min(viewport_region.height / aspect_scale, 100.0),
            ),
            "Dither": _SUPER_FX_BASE_DITHER
            * aspect_scale
            / _SUPER_FX_PIXELS_PER_ASPECT_UNIT,
        }
        updated_materials = _apply_super_fx_settings_to_all(settings)
        if not updated_materials:
            self.report({'WARNING'}, "No compatible Super FX materials found")
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Calculated settings for {viewport_region.width}x{viewport_region.height} "
            f"viewport and applied them to {updated_materials} materials",
        )
        return {'FINISHED'}


# =========================
# FastFX Menu Panel -  Palette assignment (simple)
# =========================
class OBJECT_OT_apply_material_colors_simple(bpy.types.Operator):
    """Apply colors based on material names (FX#)"""
    bl_idname = "object.apply_material_colors_simple"
    bl_label = "Apply Material Palette (Simple)"

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "No mesh object selected")
            return {'CANCELLED'}

        if not obj.data.materials:
            self.report({'WARNING'}, "No materials found on selected object")
            return {'CANCELLED'}

        for material_slot in obj.material_slots:
            material = material_slot.material
            if material:
                material_name = _palette_material_name(material)
                if not (material_name.startswith("FX") or material_name.startswith("FE")):
                    continue
                try:
                    # Extract color index and retrieve the color
                    color_index = int(material_name[2:])
                    hex_color = id_0_c_rgb.get(color_index, "#FFFFFF")  # Default to white

                    # Convert HEX to linear RGB for Blender
                    linear_rgb_color = hex_to_rgb(hex_color)

                    # Ensure the material uses nodes
                    material.use_nodes = True
                    node_tree = material.node_tree

                    # Clear existing nodes
                    nodes = node_tree.nodes
                    links = node_tree.links
                    nodes.clear()

                    # Add a new Principled BSDF node
                    bsdf_node = nodes.new(type="ShaderNodeBsdfPrincipled")
                    bsdf_node.location = (0, 0)

                    # Set the Base Color
                    bsdf_node.inputs["Base Color"].default_value = linear_rgb_color
                    bpy.data.materials[material.name].diffuse_color = linear_rgb_color

                    # Add a Material Output node
                    output_node = nodes.new(type="ShaderNodeOutputMaterial")
                    output_node.location = (300, 0)

                    # Connect the BSDF to the Surface input of the Material Output
                    links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

                except ValueError:
                    self.report({'WARNING'}, f"Material '{material.name}' has invalid FX# or FE# format")
                    continue

        self.report({'INFO'}, "Palette applied to materials")
        return {'FINISHED'}

# =========================
# FastFX Menu Panel - Add Editable ShapeHdr Properties to Object
# =========================
class AddShapeHeaderPropertiesOperator(bpy.types.Operator):
    """Add Shape Header Properties to Selected Object"""
    bl_idname = "object.add_shape_header_properties"
    bl_label = "Add ShapeHdr Properties"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object

        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a valid mesh object.")
            return {'CANCELLED'}

        # Set ShapeHdr properties on the object
        shape_header_defaults = (
            ("assembly_name", ""),
            ("zsort_priority", "0"),
            ("scale", "0"),
            ("colbox_label", "0"),
            ("color_palette", "id_0_c"),
            ("shadow_shape", "0"),
            ("close_lod_shape", "0"),
            ("mid_lod_shape", "0"),
            ("far_lod_shape", "0"),
        )
        for key, value in shape_header_defaults:
            if key not in obj:
                obj[key] = value

        self.report({'INFO'}, f"ShapeHdr properties assigned to {obj.name}")
        return {'FINISHED'}


class AdditionalShapeHeaderProperties(bpy.types.PropertyGroup):
    assembly_label: bpy.props.StringProperty(name="Assembler Label", default="")
    null_geometry_pointers: bpy.props.BoolProperty(
        name="Null Point/Face Pointers",
        description="Write 0 for the point and face pointers in this header",
        default=False,
    )
    zsort_priority: bpy.props.StringProperty(name="Z-Sort Priority", default="")
    scale: bpy.props.StringProperty(name="Scale", default="")
    colbox_label: bpy.props.StringProperty(name="Colbox Label", default="")
    color_palette: bpy.props.StringProperty(name="Color Palette", default="")
    shadow_shape: bpy.props.StringProperty(name="Shadow Shape", default="")
    close_lod_shape: bpy.props.StringProperty(name="Close LOD Shape", default="")
    mid_lod_shape: bpy.props.StringProperty(name="Mid LOD Shape", default="")
    far_lod_shape: bpy.props.StringProperty(name="Far LOD Shape", default="")


class AddAdditionalShapeHeaderOperator(bpy.types.Operator):
    """Add an additional ShapeHdr that inherits blank fields from the main header"""
    bl_idname = "object.add_additional_shape_header"
    bl_label = "Add Additional ShapeHdr"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and "zsort_priority" in obj

    def execute(self, context):
        context.active_object.fastfx_additional_shape_headers.add()
        self.report({'INFO'}, "Additional ShapeHdr added")
        return {'FINISHED'}


class RemoveAdditionalShapeHeaderOperator(bpy.types.Operator):
    """Remove an additional ShapeHdr"""
    bl_idname = "object.remove_additional_shape_header"
    bl_label = "Remove Additional ShapeHdr"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        headers = context.active_object.fastfx_additional_shape_headers
        if self.index < 0 or self.index >= len(headers):
            self.report({'ERROR'}, "Additional ShapeHdr no longer exists")
            return {'CANCELLED'}
        headers.remove(self.index)
        return {'FINISHED'}


def register_shape_header_settings():
    bpy.types.Object.fastfx_additional_shape_headers = bpy.props.CollectionProperty(
        type=AdditionalShapeHeaderProperties,
    )


def unregister_shape_header_settings():
    del bpy.types.Object.fastfx_additional_shape_headers


# =========================
# FastFX Menu Panel - Select twisted faces in Edit Mode
# =========================
class OBJECT_OT_select_twisted_faces(bpy.types.Operator):
    """Select faces whose vertices twist away from a single plane"""
    bl_idname = "object.select_twisted_faces"
    bl_label = "Select Twisted Faces"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.object.type == 'MESH'
            and context.mode == 'EDIT_MESH'
        )

    @staticmethod
    def _face_twist(face):
        if len(face.verts) <= 3:
            return 0.0

        a = face.verts[0].co
        b = face.verts[1].co
        c = face.verts[2].co

        ux = b.x - a.x
        uy = b.y - a.y
        uz = b.z - a.z
        vx = c.x - a.x
        vy = c.y - a.y
        vz = c.z - a.z

        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        magnitude = math.sqrt(nx * nx + ny * ny + nz * nz)

        if magnitude <= 1e-12:
            return 0.0

        nx /= magnitude
        ny /= magnitude
        nz /= magnitude

        plane_d = nx * a.x + ny * a.y + nz * a.z
        total_distance = 0.0

        for vert in face.verts:
            v = vert.co
            distance = nx * v.x + ny * v.y + nz * v.z - plane_d
            total_distance += distance * distance

        return total_distance / magnitude

    def execute(self, context):
        obj = context.object

        bm = bmesh.from_edit_mesh(obj.data)
        selected_count = 0
        total_twist = 0.0
        polygon_count = 0

        for face in bm.faces:
            face.select = False
            if len(face.verts) <= 2:
                continue

            polygon_count += 1
            twist = self._face_twist(face)
            total_twist += twist

            if len(face.verts) > 3 and twist > 0.01:
                face.select = True
                selected_count += 1

        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        average_twist = (total_twist * 100.0 / polygon_count) if polygon_count else 0.0
        self.report({'INFO'}, f"Avg twist {average_twist:.6f}% | Selected {selected_count} twisted faces")
        return {'FINISHED'}


class OBJECT_OT_select_unmirrored_vertices(bpy.types.Operator):
    """Select vertices without a matching point reflected across local X"""
    bl_idname = "object.select_unmirrored_vertices"
    bl_label = "Select Points Not X-Mirrored"
    bl_options = {'REGISTER', 'UNDO'}

    tolerance: bpy.props.FloatProperty(
        name="Match Tolerance",
        description="Maximum distance from the reflected point to count as a match",
        default=0.0,
        min=0.0,
        subtype='DISTANCE',
    )

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.object.type == 'MESH'
            and context.mode == 'EDIT_MESH'
        )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    @staticmethod
    def _unmirrored_indices(vertices, tolerance):
        if not vertices:
            return []

        if tolerance == 0.0:
            coordinate_indices = {}
            for index, vertex in enumerate(vertices):
                coordinate_indices.setdefault(tuple(vertex.co), []).append(index)

            unmirrored_indices = []
            for index, vertex in enumerate(vertices):
                if vertex.co.x == 0.0:
                    continue
                reflected = (-vertex.co.x, vertex.co.y, vertex.co.z)
                if not any(
                    other_index != index
                    for other_index in coordinate_indices.get(reflected, ())
                ):
                    unmirrored_indices.append(index)
            return unmirrored_indices

        tree = KDTree(len(vertices))
        for index, vertex in enumerate(vertices):
            tree.insert(vertex.co, index)
        tree.balance()

        unmirrored_indices = []
        for index, vertex in enumerate(vertices):
            if vertex.co.x == 0.0:
                continue
            reflected = vertex.co.copy()
            reflected.x = -reflected.x
            has_match = any(
                other_index != index
                for _, other_index, _ in tree.find_range(
                    reflected,
                    math.nextafter(tolerance, math.inf),
                )
            )
            if not has_match:
                unmirrored_indices.append(index)
        return unmirrored_indices

    def execute(self, context):
        obj = context.object
        context.tool_settings.mesh_select_mode = (True, False, False)
        bm = bmesh.from_edit_mesh(obj.data)
        bm.select_mode = {'VERT'}
        vertices = list(bm.verts)
        unmirrored_indices = self._unmirrored_indices(vertices, self.tolerance)

        for element in (*bm.verts, *bm.edges, *bm.faces):
            element.select = False
        for index in unmirrored_indices:
            vertices[index].select = True
        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        self.report(
            {'INFO'},
            f"Selected {len(unmirrored_indices)} points without X-mirrored matches",
        )
        return {'FINISHED'}


# =========================
# FastFX Menu Panel - Nondestructive merge by distance
# =========================
class OBJECT_OT_merge_points_by_distance(bpy.types.Operator):
    """Merge nearby selected vertices while retaining every polygon"""
    bl_idname = "object.merge_points_by_distance"
    bl_label = "Merge Points (Keep Faces)"
    bl_options = {'REGISTER', 'UNDO'}

    distance: bpy.props.FloatProperty(
        name="Distance",
        description="Maximum distance between points to merge",
        default=0.0001,
        min=0.0,
        subtype='DISTANCE',
    )

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.object.type == 'MESH'
            and context.mode == 'EDIT_MESH'
        )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    @staticmethod
    def _vertex_groups(vertices, faces, distance):
        selected = [index for index, vertex in enumerate(vertices) if vertex.select]
        parent = list(range(len(vertices)))
        conflicts = {index: set() for index in selected}

        for face in faces:
            face_selected = [index for index in face if index in conflicts]
            for offset, first in enumerate(face_selected):
                for second in face_selected[offset + 1:]:
                    conflicts[first].add(second)
                    conflicts[second].add(first)

        pairs = []
        if distance == 0.0:
            coincident = {}
            for index in selected:
                key = tuple(vertices[index].co)
                coincident.setdefault(key, []).append(index)
            for indices in coincident.values():
                pairs.extend(
                    (first, second, 0.0)
                    for offset, first in enumerate(indices)
                    for second in indices[offset + 1:]
                )
        else:
            buckets = {}
            for index in selected:
                coordinate = vertices[index].co
                cell = tuple(math.floor(value / distance) for value in coordinate)
                for x in range(cell[0] - 1, cell[0] + 2):
                    for y in range(cell[1] - 1, cell[1] + 2):
                        for z in range(cell[2] - 1, cell[2] + 2):
                            for other in buckets.get((x, y, z), ()):
                                delta = vertices[index].co - vertices[other].co
                                squared_distance = delta.length_squared
                                if squared_distance <= distance * distance:
                                    pairs.append((other, index, squared_distance))
                buckets.setdefault(cell, []).append(index)

        pairs.sort(key=lambda pair: (pair[2], pair[0], pair[1]))
        for first, second, _ in pairs:
            first_root = parent[first]
            while parent[first_root] != first_root:
                first_root = parent[first_root]
            second_root = parent[second]
            while parent[second_root] != second_root:
                second_root = parent[second_root]
            if first_root == second_root or second_root in conflicts[first_root]:
                continue

            root, absorbed = sorted((first_root, second_root))
            neighbors = (conflicts[root] | conflicts[absorbed]) - {root, absorbed}
            parent[absorbed] = root
            conflicts[root] = neighbors
            conflicts.pop(absorbed)
            for neighbor in neighbors:
                conflicts[neighbor].discard(root)
                conflicts[neighbor].discard(absorbed)
                conflicts[neighbor].add(root)

        for index in range(len(parent)):
            root = index
            while parent[root] != root:
                root = parent[root]
            parent[index] = root
        return parent, selected

    @staticmethod
    def _attribute_property_name(data_type):
        property_name = {
            'FLOAT': "value",
            'INT': "value",
            'BOOLEAN': "value",
            'STRING': "value",
            'INT8': "value",
            'FLOAT_VECTOR': "vector",
            'FLOAT2': "vector",
            'FLOAT_COLOR': "color",
            'BYTE_COLOR': "color",
            'QUATERNION': "value",
            'FLOAT4X4': "value",
        }.get(data_type)
        if property_name is None:
            raise ValueError(f"Unsupported mesh attribute data type: {data_type}")
        return property_name

    @classmethod
    def _attribute_value(cls, item, data_type):
        return getattr(item, cls._attribute_property_name(data_type))

    @classmethod
    def _copy_attributes(cls, source, target, point_sources, edge_sources):
        built_in_attributes = {"position", "material_index", "sharp_face"}
        for attribute in source.attributes:
            if (
                attribute.name.startswith(".")
                or attribute.name in built_in_attributes
                or getattr(attribute, "is_internal", False)
            ):
                continue
            if attribute.domain not in {'POINT', 'EDGE', 'FACE', 'CORNER'}:
                continue
            values = [
                cls._attribute_value(item, attribute.data_type)
                for item in attribute.data
            ]
            if attribute.domain == 'POINT':
                source_indices = point_sources
            elif attribute.domain == 'EDGE':
                source_indices = edge_sources
            else:
                source_indices = range(len(values))
            target_domain_size = {
                'POINT': len(target.vertices),
                'EDGE': len(target.edges),
                'FACE': len(target.polygons),
                'CORNER': len(target.loops),
            }[attribute.domain]
            if len(source_indices) != target_domain_size:
                raise ValueError(
                    f"Could not preserve mesh attribute '{attribute.name}'."
                )
            copied = target.attributes.new(
                name=attribute.name,
                type=attribute.data_type,
                domain=attribute.domain,
            )
            property_name = cls._attribute_property_name(attribute.data_type)
            for target_index, source_index in enumerate(source_indices):
                if source_index is not None:
                    setattr(copied.data[target_index], property_name, values[source_index])

    def execute(self, context):
        obj = context.object
        if obj.data.shape_keys is not None:
            self.report(
                {'ERROR'},
                "Merge points before creating shape keys; changing topology invalidates their vertex data.",
            )
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='OBJECT')
        source = obj.data
        vertices = list(source.vertices)
        faces = [tuple(polygon.vertices) for polygon in source.polygons]
        selected = [index for index, vertex in enumerate(vertices) if vertex.select]
        if len(selected) < 2:
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'WARNING'}, "Select at least two vertices to merge.")
            return {'CANCELLED'}

        groups, _ = self._vertex_groups(vertices, faces, self.distance)
        representatives = {}
        for index, root in enumerate(groups):
            representatives[root] = min(index, representatives.get(root, index))
        if len(representatives) == len(vertices):
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'INFO'}, "No selected points were within the merge distance.")
            return {'CANCELLED'}

        roots = sorted(representatives)
        root_to_new = {root: index for index, root in enumerate(roots)}
        vertex_map = [root_to_new[root] for root in groups]
        new_vertices = [vertices[representatives[root]].co[:] for root in roots]
        new_faces = [tuple(vertex_map[index] for index in face) for face in faces]
        new_edges = []
        edge_sources = {}
        for edge in source.edges:
            mapped = tuple(vertex_map[index] for index in edge.vertices)
            if mapped[0] == mapped[1]:
                continue
            key = tuple(sorted(mapped))
            if key not in edge_sources:
                edge_sources[key] = edge.index
                new_edges.append(mapped)

        new_mesh = None
        try:
            new_mesh = bpy.data.meshes.new(source.name)
            new_mesh.from_pydata(new_vertices, new_edges, new_faces)
            new_mesh.update()
            for material in source.materials:
                new_mesh.materials.append(material)
            for index, polygon in enumerate(source.polygons):
                new_mesh.polygons[index].material_index = polygon.material_index
                new_mesh.polygons[index].use_smooth = polygon.use_smooth
                new_mesh.polygons[index].select = polygon.select
            for edge in new_mesh.edges:
                edge.select = source.edges[edge_sources[tuple(sorted(edge.vertices))]].select
            selected_roots = {groups[index] for index in selected}
            for new_index, root in enumerate(roots):
                new_mesh.vertices[new_index].select = root in selected_roots

            point_sources = [representatives[root] for root in roots]
            edge_source_indices = [
                edge_sources.get(tuple(sorted(edge.vertices)))
                for edge in new_mesh.edges
            ]
            self._copy_attributes(source, new_mesh, point_sources, edge_source_indices)
        except (RuntimeError, TypeError, ValueError) as exc:
            if new_mesh is not None and new_mesh.users == 0:
                bpy.data.meshes.remove(new_mesh)
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'ERROR'}, f"Could not rebuild mesh while preserving its data: {exc}")
            return {'CANCELLED'}

        obj.data = new_mesh
        if source.users == 0:
            bpy.data.meshes.remove(source)
        bpy.ops.object.mode_set(mode='EDIT')
        merged_count = len(vertices) - len(new_vertices)
        self.report(
            {'INFO'},
            f"Merged {merged_count} point(s); retained all {len(new_faces)} faces.",
        )
        return {'FINISHED'}

# =========================
# FastFX Menu Panel - Assign colors to loose edges
# =========================
class OBJECT_OT_assign_edge_material(bpy.types.Operator):
    """Assign the active FX material to selected loose edges for 3DG1 export"""
    bl_idname = "object.assign_edge_material"
    bl_label = "Assign FX Material to Edges"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.object.type == 'MESH'
            and context.mode == 'EDIT_MESH'
        )

    def execute(self, context):
        obj = context.object
        material = obj.active_material
        if material is None:
            self.report({'WARNING'}, "Select an FX material in the active material slot")
            return {'CANCELLED'}

        material_name = re.sub(r"\.\d{3}$", "", material.name)
        if not material_name.startswith("FX") or not material_name[2:].isdigit():
            self.report({'WARNING'}, "The active material must be named FX followed by a color index")
            return {'CANCELLED'}
        color_index = int(material_name[2:])

        bm = bmesh.from_edit_mesh(obj.data)
        selected_edges = [edge for edge in bm.edges if edge.select]
        if not selected_edges:
            self.report({'WARNING'}, "Select one or more edges in Edit Mode")
            return {'CANCELLED'}

        loose_edges = [edge for edge in selected_edges if not edge.link_faces]
        if not loose_edges:
            self.report({'WARNING'}, "Selected edges belong to faces; only loose edges can be assigned")
            return {'CANCELLED'}

        layer = bm.edges.layers.int.get(EDGE_COLOR_ATTRIBUTE)
        if layer is None:
            layer = bm.edges.layers.int.new(EDGE_COLOR_ATTRIBUTE)
            for edge in bm.edges:
                edge[layer] = -1

        for edge in loose_edges:
            edge[layer] = color_index

        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        skipped_count = len(selected_edges) - len(loose_edges)
        message = f"Assigned FX{color_index} to {len(loose_edges)} loose edge(s)"
        if skipped_count:
            message += f"; skipped {skipped_count} edge(s) used by faces"
        self.report({'INFO'}, message)
        return {'FINISHED'}


class OBJECT_OT_convert_two_point_faces(bpy.types.Operator):
    """Convert 2-point faces on selected static mesh objects to tagged loose edges"""
    bl_idname = "object.convert_two_point_faces"
    bl_label = "Convert 2-Gons to Edges"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'OBJECT'
            and any(obj.type == 'MESH' for obj in context.selected_objects)
        )

    def execute(self, context):
        processed_meshes = set()
        converted_faces = 0
        skipped_animated = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            if is_mesh_animated(obj) or any(
                other.data is obj.data and is_mesh_animated(other)
                for other in bpy.data.objects
            ):
                skipped_animated += 1
                continue
            mesh_key = obj.data.as_pointer()
            if mesh_key in processed_meshes:
                continue
            processed_meshes.add(mesh_key)
            converted_faces += convert_two_point_faces_to_edges(obj)

        if converted_faces == 0 and skipped_animated == 0:
            self.report({'INFO'}, "No 2-point faces found on the selected mesh objects")
        else:
            message = f"Converted {converted_faces} 2-point face(s) to tagged edge(s)"
            if skipped_animated:
                message += f"; skipped {skipped_animated} animated object(s)"
            self.report({'INFO'}, message)
        return {'FINISHED'}


# =========================
# FastFX Menu Panel - 2-point face primitive
# =========================
class OBJECT_OT_add_2_point_face(bpy.types.Operator):
    """Create a 2-point face primitive"""
    bl_idname = "object.add_2_point_face"
    bl_label = "Add Real 2-Gon (OLD)"
    bl_options = {'REGISTER', 'UNDO'}

    template_name = "two-point-face"

    def _build_template(self):
        return """3DG1
2
0 -2 0
0 2 0
2 1 0 43
\x1A
"""

    def _find_template_object(self, obj=None):
        for candidate in bpy.data.objects:
            if candidate.type != 'MESH':
                continue
            if candidate.name.startswith(self.template_name):
                if obj is not None and candidate.name == obj.name:
                    continue
                return candidate
        return None

    def _import_template(self, context):
        fd, temp_path = tempfile.mkstemp(prefix=f"{self.template_name}_", suffix=".3dg1")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(self._build_template())
            result = read_3dg1(temp_path, context)
            imported = self._find_template_object()
            if imported is not None:
                imported.name = self.template_name
                imported.data.name = self.template_name
            return result, imported
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    def _drop_template_material(self, imported):
        if imported is None or imported.data is None:
            return

        if not imported.data.materials:
            return

        material = imported.data.materials[0]
        if material is None:
            return

        if material.users > 1:
            imported.data.materials.clear()
            return

        imported.data.materials.clear()
        if material.name in bpy.data.materials:
            bpy.data.materials.remove(material, do_unlink=True)

    def execute(self, context):
        obj = context.object

        if context.mode == 'EDIT_MESH':
            if obj is None or obj.type != 'MESH':
                self.report({'ERROR'}, "Please select a valid mesh object to append to.")
                return {'CANCELLED'}

            bpy.ops.object.mode_set(mode='OBJECT')
            result, imported = self._import_template(context)
            if result != {'FINISHED'} or imported is None:
                self.report({'ERROR'}, "Failed to import the 2-point face template.")
                return {'CANCELLED'}

            self._drop_template_material(imported)
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            imported.select_set(True)
            context.view_layer.objects.active = obj
            bpy.ops.object.join()
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'INFO'}, "2-point face appended to the active mesh")
            return {'FINISHED'}

        result, imported = self._import_template(context)
        if result != {'FINISHED'} or imported is None:
            self.report({'ERROR'}, "Failed to create the 2-point face mesh.")
            return {'CANCELLED'}

        self._drop_template_material(imported)
        self.report({'INFO'}, "2-point face created")
        return {'FINISHED'}

# =========================
# FastFX Menu Panel - Toggle Backface Culling on all Materials
# =========================
class OBJECT_OT_toggle_backface_culling(bpy.types.Operator):
    """Toggle backface culling for all materials"""
    bl_idname = "object.toggle_backface_culling"
    bl_label = "Toggle Backface Culling on Materials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        count = 0
        for m in bpy.data.materials:
            if m is None:
                continue
            current = getattr(m, 'use_backface_culling', False)
            try:
                m.use_backface_culling = not current
                count += 1
            except Exception:
                continue
        self.report({'INFO'}, f"Toggled backface culling for {count} materials")
        return {'FINISHED'}

# =========================
# FastFX Menu Panel Layout
# =========================
class VIEW3D_PT_fastfx_tools(bpy.types.Panel):
    """Global configuration for FastFX"""
    bl_label = "FastFX Global Configuration"
    bl_idname = "VIEW3D_PT_fastfx_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FastFX"
    bl_order = 0
#    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "fastfx_game_preset")
        export_box = layout.box()
        export_box.label(text="Export Options")
        export_box.prop(scene, "fastfx_export_sort_mode")
        export_box.prop(scene, "fastfx_export_compress_point_pairs")
        simplified_row = export_box.row()
        simplified_row.enabled = scene.fastfx_game_preset not in {"STARFOX2", "STARFOXEX"}
        simplified_row.prop(scene, "fastfx_export_simplified_shapehdr")
        import_box = layout.box()
        import_box.label(text="Import Options")
        import_box.prop(scene, "fastfx_import_convert_two_point_faces")


class VIEW3D_PT_fastfx_animation(bpy.types.Panel):
    """Vertex animation controls and export settings"""
    bl_label = "Animation"
    bl_idname = "VIEW3D_PT_fastfx_animation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FastFX"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.active_object

        layout.prop(scene, "fastfx_use_legacy_animation_objects")
        frame_row = layout.row()
        frame_row.enabled = is_vertex_animation(obj)
        frame_row.prop(scene, "fastfx_static_export_frame")

        if is_vertex_animation(obj):
            animation_box = layout.box()
            animation_box.label(text="Vertex Animation")
            animation_box.label(
                text=f"Frame {obj.fastfx_animation_frame} of {animation_frame_count(obj) - 1}"
            )
            controls = animation_box.row(align=True)
            navigation_start = controls.row(align=True)
            navigation_start.enabled = (
                obj.mode == "OBJECT" and not scene.fastfx_animation_playing
            )
            first = navigation_start.operator(
                "object.fastfx_animation_jump_endpoint",
                text="",
                icon='REW',
            )
            first.endpoint = "START"
            previous = navigation_start.operator(
                "object.fastfx_animation_step_frame",
                text="",
                icon='BACK',
            )
            previous.direction = -1
            playback = controls.row(align=True)
            playback.enabled = obj.mode == "OBJECT"
            playback.operator("object.fastfx_animation_playback", text="", icon=(
                'PAUSE' if scene.fastfx_animation_playing else 'PLAY'
            ))
            navigation_end = controls.row(align=True)
            navigation_end.enabled = (
                obj.mode == "OBJECT" and not scene.fastfx_animation_playing
            )
            following = navigation_end.operator(
                "object.fastfx_animation_step_frame",
                text="",
                icon='FORWARD',
            )
            following.direction = 1
            last = navigation_end.operator(
                "object.fastfx_animation_jump_endpoint",
                text="",
                icon='FF',
            )
            last.endpoint = "END"
            frame_actions = animation_box.row(align=True)
            frame_actions.enabled = (
                obj.mode == "OBJECT" and not scene.fastfx_animation_playing
            )
            frame_actions.operator("object.fastfx_animation_add_frame", icon='ADD')
            frame_actions.operator(
                "object.fastfx_animation_insert_frame",
                text="Insert After",
                icon='ADD',
            )
            frame_actions.operator("object.fastfx_animation_remove_frame", icon='REMOVE')
            interpolation = animation_box.row()
            interpolation.enabled = (
                obj.mode == "OBJECT"
                and not scene.fastfx_animation_playing
                and animation_frame_count(obj) >= 2
            )
            interpolation.operator(
                "object.fastfx_animation_interpolate_frames",
                text="Interpolate Frames",
                icon='IPO_LINEAR',
            )
            animation_box.prop(scene, "fastfx_animation_loop")
            mirror_row = animation_box.row()
            mirror_row.enabled = scene.fastfx_animation_loop
            mirror_row.prop(scene, "fastfx_animation_mirror")
        elif obj is not None and obj.type == "MESH":
            layout.operator("object.fastfx_animation_add_frame", text="Start Animation")


class VIEW3D_PT_fastfx_material_configuration(bpy.types.Panel):
    """Material configuration for FastFX"""
    bl_label = "Material Configuration"
    bl_idname = "VIEW3D_PT_fastfx_material_configuration"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FastFX"
    bl_order = 2
#    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator(OBJECT_OT_toggle_backface_culling.bl_idname, text="Toggle Backface Culling")
        layout.operator(OBJECT_OT_create_material_range.bl_idname)
        layout.label(text="Color Palette (Simple)")
        layout.operator("object.apply_material_colors_simple")
        layout.label(text="Color Palette (Fancy)")
        layout.operator("object.create_super_fx")
        layout.operator("object.apply_material_colors")

        obj = context.object
        material = obj.active_material if obj else None
        super_fx_nodes = _super_fx_nodes(material)

        settings_box = layout.box()
        settings_box.label(text="Super FX Settings")
        if super_fx_nodes:
            for input_name in _SUPER_FX_INPUT_NAMES:
                settings_box.prop(
                    super_fx_nodes[0].inputs[input_name],
                    "default_value",
                    text=input_name,
                )
            settings_box.operator(OBJECT_OT_apply_super_fx_settings_to_all.bl_idname)
        else:
            settings_box.label(text="Active material has no Super FX node")
        settings_box.operator(OBJECT_OT_calculate_super_fx_settings.bl_idname)

        texture_box = layout.box()
        texture_box.label(text="Texture Preview (TX#)")
        texture_box.operator(OBJECT_OT_create_texture_material.bl_idname)
        if material is not None and is_texture_material(material):
            texture_box.prop(material, "fastfx_texture_source")
            texture_box.prop(material, "fastfx_texture_image")
            texture_box.operator(OBJECT_OT_load_texture_image.bl_idname, text="Load Image...")
            if material.fastfx_texture_source == "SHEET":
                texture_box.prop(material, "fastfx_texture_sheet_layout")
                row = texture_box.row(align=True)
                row.prop(material, "fastfx_texture_tile_x")
                row.prop(material, "fastfx_texture_tile_y")
                row = texture_box.row(align=True)
                row.prop(material, "fastfx_texture_tile_width")
                row.prop(material, "fastfx_texture_tile_height")
            texture_box.prop(material, "fastfx_texture_mirror")
            texture_box.operator(OBJECT_OT_apply_texture_material.bl_idname)
        else:
            texture_box.label(text="Create or select a TX# material to configure it")


class VIEW3D_PT_fastfx_mesh_utilities(bpy.types.Panel):
    """Mesh utilities for FastFX"""
    bl_label = "Mesh Utilities"
    bl_idname = "VIEW3D_PT_fastfx_mesh_utilities"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FastFX"
    bl_order = 3
#    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        is_starfox2 = scene.fastfx_game_preset == "STARFOX2"

        layout.operator(VertexOperation.bl_idname, text="Round Vertex Coordinates").operation = 'ROUND'
        layout.operator(VertexOperation.bl_idname, text="Truncate Vertex Coordinates").operation = 'TRUNCATE'
        layout.operator(OBJECT_OT_add_2_point_face.bl_idname, text="Add Real 2-Gon (OLD)")
        layout.operator(OBJECT_OT_select_twisted_faces.bl_idname, text="Select Twisted Faces")
        layout.operator(OBJECT_OT_select_unmirrored_vertices.bl_idname)
        layout.operator(OBJECT_OT_merge_points_by_distance.bl_idname)
        layout.operator(OBJECT_OT_assign_edge_material.bl_idname)
        layout.operator(OBJECT_OT_convert_two_point_faces.bl_idname)
        overlay_box = layout.box()
        overlay_box.label(text="Edge Material Overlay")
        overlay_box.prop(context.scene, "fastfx_show_edge_material_labels")
        overlay_box.prop(context.scene, "fastfx_show_edge_material_lines")
        if is_starfox2:
            slope_box = layout.box()
            slope_box.label(text="Slope Data (Star Fox 2)")
            selected_slope = selected_slope_settings(context)
            if selected_slope is not None:
                selection, settings = selected_slope
                if not selection[0]:
                    slope_box.label(text="Select a face to view its slope data")
                elif settings is None:
                    slope_box.label(text="Active face has no slope data")
                else:
                    slope_box.label(text="--Active Face Settings--")
                    slope_box.label(text=f"Slope Type: {settings['slope_type']}")
                    if settings["custom_slope_type"]:
                        slope_box.label(
                            text=f"Custom Type: {settings['custom_slope_type']}"
                        )
                    slope_box.label(
                        text=f"Slope Polygon: {'On' if settings['slope_poly'] else 'Off'}"
                    )
                    slope_box.label(
                        text=f"Animated: {'On' if settings['slope_animation'] else 'Off'}"
                    )
            slope_box.label(text="--Settings to Assign--")
            slope_box.prop(scene, "fastfx_slope_type")
            if scene.fastfx_slope_type == "CUSTOM":
                slope_box.prop(scene, "fastfx_custom_slope_type")
            slope_box.prop(scene, "fastfx_slope_poly")
            slope_box.prop(scene, "fastfx_slope_animation")
            slope_box.operator("object.assign_slope_data")
            slope_box.operator("object.clear_slope_data")
            slope_box.prop(scene, "fastfx_show_slope_labels")


class VIEW3D_PT_fastfx_collision_box_tools(bpy.types.Panel):
    """Collision box tools for FastFX"""
    bl_label = "Collision Box Tools"
    bl_idname = "VIEW3D_PT_fastfx_collision_box_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FastFX"
    bl_order = 4
#    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.operator("object.import_colboxes_clipboard")
        layout.operator("object.export_colboxes")
        layout.prop(scene, "fastfx_export_animated_colbox")
        layout.operator("object.update_colboxes")
        layout.operator("object.update_colbox_offsets")
        layout.operator("object.generate_colbox")


class VIEW3D_PT_fastfx_object_tools(bpy.types.Panel):
    """Object tools for FastFX"""
    bl_label = "Object Tools"
    bl_idname = "VIEW3D_PT_fastfx_object_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FastFX"
    bl_order = 5
#    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        is_starfox2 = scene.fastfx_game_preset == "STARFOX2"

        layout.label(text="ASM Tools")
        layout.operator("object.add_shape_header_properties")

        obj = context.active_object
        if obj is None:
            return

        if obj.type == 'MESH':
            shape_header_fields = (
                ("zsort_priority", "Z-Sort Priority"),
                ("scale", "Scale"),
                ("colbox_label", "Colbox Label"),
                ("color_palette", "Color Palette"),
                ("shadow_shape", "Shadow Shape"),
                ("close_lod_shape", "Close LOD Shape"),
                ("mid_lod_shape", "Mid LOD Shape"),
                ("far_lod_shape", "Far LOD Shape"),
            )
            box = layout.box()
            box.label(text="ShapeHdr Properties")
            if "zsort_priority" in obj:
                if "assembly_name" in obj:
                    box.prop(obj, '["assembly_name"]', text="Assembly Name")
                for key, label in shape_header_fields:
                    if scene.fastfx_game_preset == "STARFOXEX" and key in {
                        "close_lod_shape",
                        "mid_lod_shape",
                        "far_lod_shape",
                    }:
                        continue
                    if key in obj:
                        if key == "close_lod_shape" and is_starfox2:
                            label = "Slope Label"
                        box.prop(obj, f'["{key}"]', text=label)

                additional_box = box.box()
                additional_box.label(text="Additional ShapeHdrs")
                additional_box.operator("object.add_additional_shape_header", icon='ADD')
                additional_fields = (
                    ("assembly_label", "Assembler Label"),
                    ("zsort_priority", "Z-Sort Priority"),
                    ("scale", "Scale"),
                    ("colbox_label", "Colbox Label"),
                    ("color_palette", "Color Palette"),
                    ("shadow_shape", "Shadow Shape"),
                    ("close_lod_shape", "Close LOD Shape"),
                    ("mid_lod_shape", "Mid LOD Shape"),
                    ("far_lod_shape", "Far LOD Shape"),
                )
                for index, header in enumerate(obj.fastfx_additional_shape_headers):
                    header_box = additional_box.box()
                    header_row = header_box.row()
                    header_row.label(text=f"Header {index + 1}")
                    remove = header_row.operator(
                        "object.remove_additional_shape_header",
                        text="",
                        icon='REMOVE',
                    )
                    remove.index = index
                    header_box.prop(
                        header,
                        "null_geometry_pointers",
                        text="Null Point/Face Pointers",
                    )
                    for key, label in additional_fields:
                        if scene.fastfx_game_preset == "STARFOXEX" and key in {
                            "close_lod_shape",
                            "mid_lod_shape",
                            "far_lod_shape",
                        }:
                            continue
                        if key == "close_lod_shape" and is_starfox2:
                            label = "Slope Label"
                        header_box.prop(header, key, text=label)
            else:
                box.label(text="Add ShapeHdr Properties to edit these values")
        elif obj.type == 'EMPTY' and "colbox_label" in obj:
            colbox_fields = (
                ("colbox_label", "Label"),
                ("colbox_linked_label", "Linked Label"),
                ("colbox_offset", "Offset"),
                ("colbox_rotation", "Rotation"),
                ("colbox_dimensions", "Dimensions"),
                ("colbox_flags_set", "Flags Set"),
                ("colbox_flags_clear", "Flags Clear"),
                ("colbox_scale", "Scale"),
            )
            box = layout.box()
            box.label(text="Colbox Properties")
            for key, label in colbox_fields:
                if key in obj:
                    box.prop(obj, f'["{key}"]', text=label)
