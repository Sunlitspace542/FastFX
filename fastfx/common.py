import bpy
import bmesh
import math

# FastFX
# File: common.py
# Functions shared across multiple components.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

# =========================
# Hex color to RGB color Converter
# =========================
def srgb_to_linearrgb(c):
    if c < 0:
        return 0
    elif c < 0.04045:
        return c / 12.92
    else:
        return ((c + 0.055) / 1.055) ** 2.4

def hex_to_rgb(hex_color, alpha=1.0):
    """Converts a hex color code to Blender-compatible linear RGB values."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (srgb_to_linearrgb(r), srgb_to_linearrgb(g), srgb_to_linearrgb(b), alpha)

# =========================
# Vertex Operations Logic
# =========================
class VertexOperation(bpy.types.Operator):
    """Perform vertex operations"""
    bl_idname = "object.vertex_operation"
    bl_label = "Modify Vertex Coordinates"
    bl_options = {'REGISTER', 'UNDO'}

    operation: bpy.props.EnumProperty(
        items=[
            ('ROUND', "Round", "Round vertex coordinates to the nearest integer"),
            ('TRUNCATE', "Truncate", "Truncate vertex coordinates to their integer parts")
        ],
        name="Operation",
        description="Choose how to modify vertex coordinates",
        default='ROUND'
    )

    def execute(self, context):
        obj = context.active_object

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "No active mesh object selected")
            return {'CANCELLED'}

        # Access the mesh data
        mesh = obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh)

        for vert in bm.verts:
            if self.operation == 'ROUND':
                vert.co[0] = round(vert.co[0], 0)
                vert.co[1] = round(vert.co[1], 0)
                vert.co[2] = round(vert.co[2], 0)
            elif self.operation == 'TRUNCATE':
                vert.co[0] = math.trunc(vert.co[0])
                vert.co[1] = math.trunc(vert.co[1])
                vert.co[2] = math.trunc(vert.co[2])

        # Update the mesh
        bm.to_mesh(mesh)
        bm.free()

        return {'FINISHED'}

