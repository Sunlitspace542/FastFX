import bpy
import bmesh
import math
import os
import tempfile

from .common import VertexOperation, hex_to_rgb
from .fmt_3dg1 import read_3dg1
from .palette import id_0_c_components_rgb, id_0_c_rgb
from .superfx import super_fx_node_group

# FastFX
# File: ui.py
# FastFX menu panel functions.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

# =========================
# FastFX Menu Panel -  Palette assignment (fancy)
# =========================
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

        for material_slot in obj.material_slots:
            material = material_slot.material
            if material and (material.name.startswith("FX") or material.name.startswith("FE")):
                try:
                    # Extract color index from the material name
                    color_index = int(material.name[2:])
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
                    super_fx.node_tree = bpy.data.node_groups["Super FX"]
                    super_fx.location = (0, 0)

                    # Link Super FX to material output
                    links.new(super_fx.outputs["Emission"], output_node.inputs["Surface"])

                    # Assign colors to the Super FX node group inputs
                    for input_name, value in settings.items():
                        if input_name.startswith("Colour"):
                            # Process color inputs
                            if input_name in super_fx.inputs:
                                super_fx.inputs[input_name].default_value = hex_to_rgb(value)
                        else:
                            # Handle other material settings
                            if input_name == "Carry Over":
                                try:
                                    super_fx.inputs[input_name].default_value = float(value)
                                except ValueError:
                                    self.report({'WARNING'}, f"Invalid value for '{input_name}' in material '{material.name}'")

                except ValueError:
                    self.report({'WARNING'}, f"Material '{material.name}' has invalid FX# or FE# format")
                    continue

        self.report({'INFO'}, "Palette applied to materials")
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
            if material and (material.name.startswith("FX") or material.name.startswith("FE")):
                try:
                    # Extract color index and retrieve the color
                    color_index = int(material.name[2:])
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
        obj["zsort_priority"] = "0"
        obj["scale"] = "0"
        obj["colbox_label"] = "0"
        obj["color_palette"] = "id_0_c"
        obj["shadow_shape"] = "0"
        obj["close_lod_shape"] = "0"
        obj["mid_lod_shape"] =  "0"
        obj["far_lod_shape"] =  "0"

        self.report({'INFO'}, f"ShapeHdr properties assigned to {obj.name}")
        return {'FINISHED'}

# =========================
# FastFX Menu Panel - Select twisted faces in Edit Mode
# =========================
class OBJECT_OT_select_twisted_faces(bpy.types.Operator):
    """Select faces whose vertices twist away from a single plane"""
    bl_idname = "object.select_twisted_faces"
    bl_label = "Select Twisted Faces"
    bl_options = {'REGISTER', 'UNDO'}

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
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a valid mesh object.")
            return {'CANCELLED'}

        is_edit_mode = (context.mode == 'EDIT_MESH') or getattr(obj, 'mode', None) == 'EDIT'
        if not is_edit_mode:
            self.report({'WARNING'}, "This operator must be run in Edit Mode.")
            return {'CANCELLED'}

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

# =========================
# FastFX Menu Panel - 2-point face primitive
# =========================
class OBJECT_OT_add_2_point_face(bpy.types.Operator):
    """Create a 2-point face primitive"""
    bl_idname = "object.add_2_point_face"
    bl_label = "Add 2-Point Face"
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
    """FastFX tools"""
    bl_label = "FastFX"
    bl_idname = "VIEW3D_PT_fastfx_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FastFX"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Material Configuration")
        layout.operator(OBJECT_OT_toggle_backface_culling.bl_idname, text="Toggle Backface Culling")
        layout.label(text="Color Palette (Fancy)")
        layout.operator("object.create_super_fx")
        layout.operator("object.apply_material_colors")
        layout.label(text="Color Palette (Simple)")
        layout.operator("object.apply_material_colors_simple")
        layout.label(text="Mesh Utilities")
        layout.operator(VertexOperation.bl_idname, text="Round Vertex Coordinates").operation = 'ROUND'
        layout.operator(VertexOperation.bl_idname, text="Truncate Vertex Coordinates").operation = 'TRUNCATE'
        layout.operator(OBJECT_OT_add_2_point_face.bl_idname, text="Add 2-Point Face")
        layout.operator(OBJECT_OT_select_twisted_faces.bl_idname, text="Select Twisted Faces")
        layout.label(text="Collision Box Tools")
        layout.operator("object.import_colboxes_clipboard")
        layout.operator("object.export_colboxes")
        layout.operator("object.update_colboxes")
        layout.operator("object.update_colbox_offsets")
        layout.operator("object.generate_colbox")
        layout.label(text="BSP/GZS Tools")
        layout.operator("object.add_shape_header_properties")


