# FastFX
# File: common.py
# Functions shared across multiple components.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

import bpy
import bmesh
import math

EDGE_COLOR_ATTRIBUTE = "fastfx_edge_color_index"
LEGACY_ANIMATION_FRAME_MARKER = "fastfx_legacy_animation_frame"


def is_mesh_animated(obj):
    return (
        obj is not None
        and obj.type == "MESH"
        and (
            obj.data.shape_keys is not None
            or obj.animation_data is not None
            or obj.data.animation_data is not None
            or bool(obj.get(LEGACY_ANIMATION_FRAME_MARKER, False))
        )
    )


def convert_two_point_faces_to_edges(obj):
    """Replace 2-point faces with loose edges tagged for 3DG1 export."""
    if obj is None or obj.type != "MESH":
        raise ValueError("A mesh object is required.")
    if is_mesh_animated(obj):
        raise ValueError(f"Cannot convert 2-point faces on animated object '{obj.name}'.")

    mesh = obj.data
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        faces = [face for face in bm.faces if len(face.verts) == 2]
        if not faces:
            return 0

        edge_color = bm.edges.layers.int.get(EDGE_COLOR_ATTRIBUTE)
        if edge_color is None:
            edge_color = bm.edges.layers.int.new(EDGE_COLOR_ATTRIBUTE)
            for edge in bm.edges:
                edge[edge_color] = -1

        tagged_edges = []
        for face in faces:
            edge = bm.edges.get((face.verts[0], face.verts[1]))
            if edge is None:
                raise RuntimeError("Could not find the edge for a 2-point face.")

            material_index = face.material_index
            material = (
                mesh.materials[material_index]
                if 0 <= material_index < len(mesh.materials)
                else None
            )
            color_index = material_index
            if material is not None:
                material_name = material.name.rsplit(".", 1)[0]
                if (
                    material_name.startswith(("FX", "FE"))
                    and material_name[2:].isdigit()
                ):
                    color_index = int(material_name[2:])
            if edge[edge_color] < 0:
                edge[edge_color] = color_index
            tagged_edges.append(face)

        for face in tagged_edges:
            bm.faces.remove(face)
        bm.to_mesh(mesh)
        mesh.update()
        return len(tagged_edges)
    finally:
        bm.free()


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
    """Place exact inverse-X pairs first, followed by non-mirrored vertices.

    Exact inverse-X pairs are grouped at the start so downstream writers can
    encode them in a contiguous ``PointsX`` run. When requested, nearest-
    neighbor fallback pairs follow the mirrored pairs.
    """
    sorted_indices = sorted(range(len(vertices)), key=lambda i: distance_from_origin(vertices[i]))
    remaining_indices = list(sorted_indices)
    mirrored_pairs = []
    fallback_pairs = []
    unpaired_indices = []

    while remaining_indices:
        current_index = remaining_indices.pop(0)
        current_point = vertices[current_index]
        best_match = None
        best_distance = float('inf')
        exact_match = False

        # Try to find a pair with an inverse-X point
        for candidate_index in remaining_indices:
            candidate_point = vertices[candidate_index]
            if current_point[1:] == candidate_point[1:] and current_point[0] == -candidate_point[0]:
                best_match = candidate_index
                exact_match = True
                break

            if prefer_closest_fallback:
                # Measure distance for fallback pairing
                dist = sum((current_point[i] - candidate_point[i]) ** 2 for i in range(3))
                if dist < best_distance:
                    best_distance = dist
                    best_match = candidate_index

        if best_match is not None:
            pair = (current_index, best_match)
            (mirrored_pairs if exact_match else fallback_pairs).append(pair)
            remaining_indices.remove(best_match)
        else:
            unpaired_indices.append(current_index)

    ordered_indices = [
        index
        for pair in mirrored_pairs + fallback_pairs
        for index in pair
    ] + unpaired_indices
    new_vertices = [vertices[index] for index in ordered_indices]
    index_map = {old_index: new_index for new_index, old_index in enumerate(ordered_indices)}

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
