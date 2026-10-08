import os
import struct

import bpy

from .common import hex_to_rgb
from .palette import id_0_c_rgb

# FastFX
# File: fmt_cad.py
# Functions dealing with Iwamoto-CAD CAD/NCA file import.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

_CAD_RECORD_SIZES = {
    0: 40,   # Object: 68k-aligned doubles
    1: 14,   # Polygon: trailing byte plus structure padding
    2: 32,   # Point: 68k-aligned doubles
    3: 130,  # Animation index: flag, alignment byte, 64 shorts
    4: 32,   # Animated point
}


def read_cad(filepath):
    """Read a big-endian Iwamoto CAD/NCA file into frame vertices and polygons."""
    with open(filepath, "rb") as file:
        data = file.read()

    records = {record_type: {} for record_type in _CAD_RECORD_SIZES}
    offset = 0
    while offset < len(data):
        if len(data) - offset < 3:
            raise ValueError("Truncated CAD record header")

        record_type = data[offset]
        if record_type not in _CAD_RECORD_SIZES:
            raise ValueError(f"Unsupported CAD record type: {record_type}")

        record_index = struct.unpack_from(">h", data, offset + 1)[0]
        if record_index < 0:
            raise ValueError(f"Invalid negative CAD record index: {record_index}")

        record_start = offset + 3
        record_end = record_start + _CAD_RECORD_SIZES[record_type]
        if record_end > len(data):
            raise ValueError(f"Truncated CAD record {record_type}:{record_index}")
        if record_index in records[record_type]:
            raise ValueError(f"Duplicate CAD record {record_type}:{record_index}")

        record = data[record_start:record_end]
        if record_type == 0:
            fields = struct.unpack_from(">hhhh", record, 2)
            records[record_type][record_index] = {"first_polygon": fields[3]}
        elif record_type == 1:
            next_polygon, first_point, animation, _both = struct.unpack_from(">hhhh", record, 2)
            records[record_type][record_index] = {
                "next_polygon": next_polygon,
                "first_point": first_point,
                "animation": animation,
                "color": record[11],
                "point_count": record[12],
            }
        elif record_type in (2, 4):
            next_point = struct.unpack_from(">h", record, 2)[0]
            coordinates = struct.unpack_from(">ddd", record, 8)
            records[record_type][record_index] = {
                "next_point": next_point,
                "coordinates": coordinates,
            }
        else:
            records[record_type][record_index] = struct.unpack_from(">64h", record, 2)

        offset = record_end

    root = records[0].get(0)
    if root is None:
        raise ValueError("CAD file has no root object record")

    def follow_point_chain(record_type, first_point, expected_count):
        points = []
        visited = set()
        point_index = first_point
        while point_index != -1:
            if point_index in visited:
                raise ValueError(f"Cycle in CAD point chain at record {point_index}")
            visited.add(point_index)
            point = records[record_type].get(point_index)
            if point is None:
                raise ValueError(f"Missing CAD point record {record_type}:{point_index}")
            points.append(point["coordinates"])
            point_index = point["next_point"]

        if len(points) != expected_count:
            raise ValueError(
                f"CAD polygon has {expected_count} points but its linked list contains {len(points)}"
            )
        return points

    polygons = []
    polygon_index = root["first_polygon"]
    visited_polygons = set()
    animation_lengths = set()
    while polygon_index != -1:
        if polygon_index in visited_polygons:
            raise ValueError(f"Cycle in CAD polygon chain at record {polygon_index}")
        visited_polygons.add(polygon_index)
        polygon = records[1].get(polygon_index)
        if polygon is None:
            raise ValueError(f"Missing CAD polygon record 1:{polygon_index}")

        animation_frames = None
        if polygon["animation"] != -1:
            frame_indices = records[3].get(polygon["animation"])
            if frame_indices is None:
                raise ValueError(f"Missing CAD animation index record 3:{polygon['animation']}")
            frame_count = next(
                (frame for frame, point_index in enumerate(frame_indices) if point_index == -1),
                len(frame_indices),
            )
            if any(point_index != -1 for point_index in frame_indices[frame_count:]):
                raise ValueError("CAD animation index has a frame after its terminator")
            if frame_count == 0:
                raise ValueError(f"CAD animation index {polygon['animation']} contains no frames")
            animation_lengths.add(frame_count)
            animation_frames = [
                follow_point_chain(4, first_point, polygon["point_count"])
                for first_point in frame_indices[:frame_count]
            ]

        polygons.append({
            "color": polygon["color"],
            "static_points": follow_point_chain(2, polygon["first_point"], polygon["point_count"]),
            "animation_frames": animation_frames,
        })
        polygon_index = polygon["next_polygon"]

    if not polygons:
        raise ValueError("CAD file contains no polygons")
    if len(animation_lengths) > 1:
        raise ValueError("CAD polygons have inconsistent animation frame counts")
    frame_count = next(iter(animation_lengths), 1)

    frame_vertices = [[] for _ in range(frame_count)]
    mesh_polygons = []
    polygon_colors = []
    vertex_indices = {}
    for polygon in polygons:
        points_by_frame = polygon["animation_frames"]
        if points_by_frame is None:
            points_by_frame = [polygon["static_points"]] * frame_count

        face = []
        for point_index in range(len(points_by_frame[0])):
            trajectory = tuple(frame[point_index] for frame in points_by_frame)
            vertex_index = vertex_indices.get(trajectory)
            if vertex_index is None:
                vertex_index = len(frame_vertices[0])
                vertex_indices[trajectory] = vertex_index
                for frame_number, coordinates in enumerate(trajectory):
                    x, y, z = coordinates
                    frame_vertices[frame_number].append((x, -z, y))
            face.append(vertex_index)
        mesh_polygons.append(face)
        polygon_colors.append(polygon["color"])

    return frame_vertices, mesh_polygons, polygon_colors


def import_cad(filepath, context):
    """Create Blender mesh objects from an Iwamoto CAD or animated NCA file."""
    frame_vertices, polygons, polygon_colors = read_cad(filepath)
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    animated = len(frame_vertices) > 1
    material_indices = {}
    for color_index in sorted(set(polygon_colors)):
        material_name = f"FX{color_index}"
        material = bpy.data.materials.get(material_name) or bpy.data.materials.new(name=material_name)
        material.use_nodes = True
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            hex_color = id_0_c_rgb.get(color_index, "#FFFFFF")
            bsdf.inputs["Base Color"].default_value = hex_to_rgb(hex_color)
        material_indices[color_index] = len(material_indices)

    for frame_number, vertices in enumerate(frame_vertices):
        object_name = f"{base_name}_frame{frame_number}" if animated else base_name
        mesh = bpy.data.meshes.new(object_name)
        mesh.from_pydata(vertices, [], polygons)
        mesh.update()
        obj = bpy.data.objects.new(object_name, mesh)
        context.collection.objects.link(obj)

        for color_index in sorted(material_indices):
            material_name = f"FX{color_index}"
            material = bpy.data.materials.get(material_name)
            if mesh.materials.find(material_name) == -1:
                mesh.materials.append(material)
        for polygon, color_index in zip(mesh.polygons, polygon_colors):
            polygon.material_index = material_indices[color_index]


class ImportCADOperator(bpy.types.Operator):
    """Import an Iwamoto CAD or NCA file."""
    bl_idname = "import_mesh.cad"
    bl_label = "Import Iwamoto CAD/NCA"
    bl_options = {'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.cad;*.nca", options={'HIDDEN'})

    def execute(self, context):
        try:
            import_cad(self.filepath, context)
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to import CAD/NCA file: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Imported CAD/NCA file: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}