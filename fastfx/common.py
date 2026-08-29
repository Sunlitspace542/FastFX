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
# Gets distance from origin
# =========================
def distance_from_origin(point):
    return math.sqrt(point[0]**2 + point[1]**2 + point[2]**2)

# =========================
# Vertex Pairing for Compression
# =========================
def pair_points_for_compression(vertices, prefer_closest_fallback=False):
    """Pair vertices to optimize for compact format encoding.

    The default behavior prioritizes exact inverse-X matches, which is the strategy
    used by the 3DG1 export path. If prefer_closest_fallback is enabled, the code
    also keeps the nearest-neighbor fallback behavior used by the ASM exports.
    """
    sorted_indices = sorted(range(len(vertices)), key=lambda i: distance_from_origin(vertices[i]))
    new_vertices = []
    index_map = {}

    while sorted_indices:
        current_index = sorted_indices.pop(0)
        current_point = vertices[current_index]
        best_match = None
        best_distance = float('inf')

        # Try to find a pair with an inverse-X point
        for candidate_index in sorted_indices:
            candidate_point = vertices[candidate_index]
            if current_point[1:] == candidate_point[1:] and current_point[0] == -candidate_point[0]:
                best_match = candidate_index
                break

            if prefer_closest_fallback:
                # Measure distance for fallback pairing
                dist = sum((current_point[i] - candidate_point[i]) ** 2 for i in range(3))
                if dist < best_distance:
                    best_distance = dist
                    best_match = candidate_index

        # Pair and map indices
        new_vertices.append(current_point)
        index_map[current_index] = len(new_vertices) - 1

        if best_match is not None:
            new_vertices.append(vertices[best_match])
            index_map[best_match] = len(new_vertices) - 1
            sorted_indices.remove(best_match)

    return new_vertices, index_map

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

