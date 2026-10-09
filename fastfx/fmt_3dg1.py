import bpy
import math
import os
import re

from .common import hex_to_rgb, distance_from_origin, pair_points_for_compression
from .animation import animation_frame_coordinates, is_vertex_animation
from .fmt_3dan import Import3DANOperator
from .palette import id_0_c_rgb

# FastFX
# File: fmt_3dg1.py
# Functions dealing with Fundoshi-Kun format import/export.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

EDGE_COLOR_ATTRIBUTE = "fastfx_edge_color_index"

# =========================
# 3DG1 Import Operator
# =========================
class Import3DGI(bpy.types.Operator):
    """Import static and animated 3DG1/3DGI files."""
    bl_idname = "import_mesh.3dgi"
    bl_label = "Import 3DG1/3DGI/3DAN"
    bl_options = {'PRESET', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    filter_glob: bpy.props.StringProperty(default="*.txt;*.3dg1;*.anm;*.3dan*.obj;*.3dgi", options={'HIDDEN'})

    def execute(self, context):
        try:
            format_kind = detect_3dgi_format(self.filepath)
            if format_kind == "static":
                return read_3dg1(self.filepath, context)
            Import3DANOperator.import_3dan(self, self.filepath, context)
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to import model: {exc}")
            return {'CANCELLED'}
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def detect_3dgi_format(filepath):
    """Detect static versus animated 3DGI files from their scalar headers."""
    with open(filepath, "r") as file:
        magic = file.readline().strip()
        if magic == "3DG1":
            return "static"
        if magic == "3DAN":
            return "animated"
        if magic != "3DGI":
            raise ValueError(f"Unsupported model file magic: {magic or '(empty)'}")

        scalar_lines = 0
        for line in file:
            values = line.split()
            if not values:
                continue
            if len(values) != 1:
                break
            try:
                int(values[0])
            except ValueError:
                break
            scalar_lines += 1
            if scalar_lines == 2:
                return "animated"

        if scalar_lines == 1:
            return "static"
        raise ValueError("3DGI file must have one scalar header line for static data or two for animation.")


# =========================
# 3DG1 Export Operator
# =========================
class Export3DG1(bpy.types.Operator):
    """Export to 3DG1 format"""
    bl_idname = "export_mesh.3dg1"
    bl_label = "Export 3DG1/Fundoshi-Kun"
    bl_options = {'PRESET'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    def execute(self, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Selected object is not a mesh")
            return {'CANCELLED'}

        sort_mode = context.scene.fastfx_export_sort_mode
        compress_point_pairs = context.scene.fastfx_export_compress_point_pairs
        try:
            vertex_coordinates = (
                animation_frame_coordinates(obj, context.scene.fastfx_static_export_frame)
                if is_vertex_animation(obj)
                else None
            )
            write_3dg1(
                self.filepath,
                obj,
                sort_mode,
                compress_point_pairs,
                vertex_coordinates=vertex_coordinates,
            )
        except (OSError, ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, f"Failed to export 3DG1: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Exported to {self.filepath} with sorting mode: {sort_mode}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# =========================
# 3DG1 Importer
# =========================
def read_3dg1(filepath, context):
    try:
        # Extract the base name of the file (without extension) to use as object and mesh name
        base_name = os.path.splitext(os.path.basename(filepath))[0]

        with open(filepath, 'r') as file:
            # Read and validate header
            header = file.readline().strip()
            if header not in {"3DG1", "3DGI"}:
                raise ValueError("Invalid file format: Not a 3DG1 file")
                return {'CANCELLED'}

            # Read vertex count
            vertex_count = int(file.readline().strip())
            vertices = []

            # Read vertices
            for _ in range(vertex_count):
                line = file.readline().strip()
                while not line:  # Skip blank lines (M2FX compatibility)
                    line = file.readline().strip()
                x, y, z = map(float, line.split())  # Parse as float (M2FX compatibility)
                vertices.append((x, -z, y)) # Translate from 3DG1/3DAN coordinate system to Blender's (Z is up/down)

            # Read polygons
            polygons = []
            material_mapping = {}
            is_hex_color_format = False  # Detect if we are using hex colors
            for line in file:
                line = line.strip()
                if not line:  # Skip blank lines (M2FX compatibility)
                    continue
                if line == chr(0x1A):  # EOF marker
                    break
                parts = line.split()
                npoints = int(parts[0])
                indices = list(map(int, parts[1:npoints + 1]))

                # Determine if it's a hex color format
                if len(parts) > npoints + 1:
                    color_value = parts[npoints + 1]
                    if color_value.startswith("0x"):  # Hex color in BGR format
                        is_hex_color_format = True
                        color_bgr = int(color_value, 16)
                        # Convert BGR to RGB
                        color_index = ((color_bgr & 0xFF) << 16) | (color_bgr & 0xFF00) | ((color_bgr >> 16) & 0xFF)
                    else:
                        color_index = int(color_value)
                else:
                    color_index = 0  # Default to 0 if no color index or color value is present

                polygons.append((indices, color_index))
                if color_index not in material_mapping:
                    material_mapping[color_index] = f"FX{color_index}"

            # Create a new mesh in Blender
            mesh = bpy.data.meshes.new(base_name)
            mesh.from_pydata(vertices, [], [poly[0] for poly in polygons])
            obj = bpy.data.objects.new(base_name, mesh)
            context.collection.objects.link(obj)

            # Create materials and assign predefined colors
            material_list = []
            for color_index, material_name in sorted(material_mapping.items()):
                material = bpy.data.materials.get(material_name) or bpy.data.materials.new(name=material_name)
                material.use_nodes = True
                bsdf = material.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    if is_hex_color_format:
                        # Use color_index directly as it represents RGB for the hex color format
                        hex_color = f"#{color_index:06X}"
                    else:
                        # Use the id_0_c_rgb dictionary for standard color indices
                        hex_color = id_0_c_rgb.get(color_index, "#FFFFFF")  # Default to white if not defined
                    linear_rgb_color = hex_to_rgb(hex_color)
                    bsdf.inputs["Base Color"].default_value = linear_rgb_color  # Linear RGB with alpha
                material_list.append(material)
                obj.data.materials.append(material)

            # Assign materials to faces
            for poly, (_, color_index) in zip(mesh.polygons, polygons):
                material_index = sorted(material_mapping.keys()).index(color_index)
                poly.material_index = material_index

        return {'FINISHED'}

    except Exception as e:
        bpy.ops.error(
            f"Error while importing file: {e}"
        )
        return {'CANCELLED'}

# =========================
# 3DG1 Exporter
# =========================
def write_3dg1(
    filepath,
    obj,
    sort_mode="distance",
    compress_point_pairs=True,
    validate_signed_16bit=False,
    vertex_coordinates=None,
):
    """
    Exports a mesh object to 3DG1 format with customizable sorting modes and compression optimization.

    :param filepath: Path to write the 3DG1 file.
    :param obj: Blender mesh object to export.
    :param sort_mode: Sorting mode ("distance", "material", "none").
    :param compress_point_pairs: Whether to reorder vertices into compression-friendly pairs.
    :param validate_signed_16bit: Reject points outside SHAPED's signed 16-bit coordinate range.
    """
    # Open the file for writing
    with open(filepath, "w") as file:
        # Collect unique vertices and map them to indices
        source_coordinates = vertex_coordinates
        if source_coordinates is None:
            source_coordinates = [vertex.co for vertex in obj.data.vertices]
        if len(source_coordinates) != len(obj.data.vertices):
            raise ValueError(
                f"Static export frame has {len(source_coordinates)} points; "
                f"expected {len(obj.data.vertices)}."
            )
        original_vertices = [
            tuple(round(coordinate) for coordinate in coordinates)
            for coordinates in source_coordinates
        ]

        if validate_signed_16bit:
            for point_index, (x, y, z) in enumerate(original_vertices):
                for axis, coordinate in (("x", x), ("y", z), ("z", -y)):
                    if not -32768 <= coordinate <= 32767:
                        raise ValueError(
                            f"Point {point_index} {axis} coordinate {coordinate} is outside "
                            "the signed 16-bit range (-32768 to 32767)."
                        )

        if compress_point_pairs:
            new_vertices, index_map = pair_points_for_compression(original_vertices)
        else:
            new_vertices = list(original_vertices)
            index_map = {i: i for i in range(len(original_vertices))}

        # Process polygons and edges
        polygons = []
        edges = []  # Store edges for colored lines

        mesh = obj.data
        mesh.calc_loop_triangles()

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
                    edges.append((
                        index_map[v1],
                        index_map[v2],
                        color_value.value,
                    ))

        for poly in mesh.polygons:
            material_index = poly.material_index
            if material_index >= len(obj.material_slots):
                continue
            material = obj.material_slots[material_index].material
            if material:
                material_name = re.sub(r"\.\d{3}$", "", material.name)
                if material_name.startswith("FE"):  # Handle edges
                    try:
                        edge_color_index = int(material_name[2:])  # Extract color index for edges
                    except ValueError:
                        edge_color_index = 0  # Default to 0 if parsing fails

                    for i in range(len(poly.vertices)):
                        v1 = poly.vertices[i]
                        v2 = poly.vertices[(i + 1) % len(poly.vertices)]
                        edges.append((index_map[v1], index_map[v2], edge_color_index))

                elif material_name.startswith("FX"):  # Handle polygons
                    try:
                        color_index = int(material_name[2:])  # Extract color index for polygons
                    except ValueError:
                        color_index = 0  # Default to 0 if parsing fails

                    poly_vertices = [index_map[vertex] for vertex in poly.vertices]
                    centroid = tuple(
                        sum(source_coordinates[v][i] for v in poly.vertices) / len(poly.vertices)
                        for i in range(3)
                    )
                    polygons.append((poly_vertices, color_index, centroid, material_index))

        # Apply sorting based on the selected mode
        if sort_mode == "distance":
            polygons.sort(key=lambda p: distance_from_origin(p[2]))  # Sort polygons by centroid distance from origin
            edges.sort(key=lambda e: distance_from_origin(
                [(new_vertices[e[0]][i] + new_vertices[e[1]][i]) / 2 for i in range(3)]
            ))  # Sort edges by midpoint distance from origin
        elif sort_mode == "material":
            polygons.sort(key=lambda p: p[3])  # Sort by material index

        if sort_mode == "distance":
            # Reverse the order so farthest elements are written last
            polygons.reverse()
            edges.reverse()

        # Deduplicate edges that occupy the same positions and have the same color
        deduped_edges = []
        seen = set()
        for v1, v2, color_index in edges:
            p1 = tuple(round(c, 6) for c in new_vertices[v1])
            p2 = tuple(round(c, 6) for c in new_vertices[v2])
            key = (p1, p2) if p1 <= p2 else (p2, p1)
            key = (key, color_index)
            if key in seen:
                continue
            seen.add(key)
            deduped_edges.append((v1, v2, color_index))
        edges = deduped_edges

        # Write 3DG1 header
        file.write("3DG1\n")
        file.write(f"{len(new_vertices)}\n")  # Total vertex count

        # Write vertices
        for vertex in new_vertices:
            file.write(f"{vertex[0]} {vertex[2]} {-(vertex[1])}\n")  # Convert back to 3DG1 coordinate system

        # Write polygons
        for poly_vertices, color_index, _, _ in polygons:
            file.write(f"{len(poly_vertices)} ")
            file.write(" ".join(map(str, poly_vertices)) + " ")
            file.write(f"{color_index}\n")

        # Write edges
        for v1, v2, color_index in edges:
            file.write(f"2 {v1} {v2} {color_index}\n")

        # End-of-file marker
        file.write(chr(0x1A))

    return {'FINISHED'}
