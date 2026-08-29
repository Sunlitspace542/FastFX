import bpy
import math
import os

from .common import hex_to_rgb
from .palette import id_0_c_rgb

# FastFX
# File: fmt_3dg1.py
# Functions dealing with Fundoshi-Kun format import/export.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

# =========================
# 3DG1 Import Operator
# =========================
class Import3DG1(bpy.types.Operator):
    """Import a 3DG1 File"""
    bl_idname = "import_mesh.3dg1"
    bl_label = "Import 3DG1/Fundoshi-kun"
    bl_options = {'PRESET', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    # Filter to show only supported files in the file browser
    filter_glob: bpy.props.StringProperty(default="*.txt;*.3dg1;*.obj", options={'HIDDEN'})

    def execute(self, context):
        return read_3dg1(self.filepath, context)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# =========================
# 3DG1 Export Operator
# =========================
class Export3DG1(bpy.types.Operator):
    """Export to 3DG1 format"""
    bl_idname = "export_mesh.3dg1"
    bl_label = "Export 3DG1/Fundoshi-Kun"
    bl_options = {'PRESET'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    sort_mode: bpy.props.EnumProperty(
        name="Sort Mode",
        description="Choose how to sort faces and edges in the exported file",
        items=[
            ('distance', "Distance from Origin", "Sort by distance from the origin"),
            ('material', "Material Order", "Sort by material order. Last material is drawn first."),
            ('none', "No Sorting", "No sorting; use Blender's internal order")
        ],
        default='distance'
    )

    def execute(self, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Selected object is not a mesh")
            return {'CANCELLED'}

        write_3dg1(self.filepath, obj, self.sort_mode)
        self.report({'INFO'}, f"Exported to {self.filepath} with sorting mode: {self.sort_mode}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout

        # Add custom help text
        layout.label(text="3DG1/Fundoshi-Kun Export Options", icon='INFO')

        # Add dropdown for sort mode
        layout.prop(self, "sort_mode", text="Sort Mode")

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
# Gets distance from origin
# =========================
def distance_from_origin(point):
    return math.sqrt(point[0]**2 + point[1]**2 + point[2]**2)

# =========================
# 3DG1 Exporter
# =========================
def write_3dg1(filepath, obj, sort_mode="distance"):
    """
    Exports a mesh object to 3DG1 format with customizable sorting modes and compression optimization.

    :param filepath: Path to write the 3DG1 file.
    :param obj: Blender mesh object to export.
    :param sort_mode: Sorting mode ("distance", "material", "none").
    """
    # Open the file for writing
    with open(filepath, "w") as file:
        # Collect unique vertices and map them to indices
        original_vertices = [(
            round(v.co.x), round(v.co.y), round(v.co.z)
        ) for v in obj.data.vertices]

        index_map = {}
        vertex_count = 0

        # Pair points for compression
        sorted_indices = sorted(range(len(original_vertices)), key=lambda i: distance_from_origin(original_vertices[i]))
        new_vertices = []

        while sorted_indices:
            current_index = sorted_indices.pop(0)
            current_point = original_vertices[current_index]

            # Try to find a pair with an inverse-X point
            best_match = None
            for candidate_index in sorted_indices:
                candidate_point = original_vertices[candidate_index]
                if current_point[1:] == candidate_point[1:] and current_point[0] == -candidate_point[0]:
                    best_match = candidate_index
                    break

            # Add the current point
            new_vertices.append(current_point)
            index_map[current_index] = len(new_vertices) - 1

            # Add its pair if found
            if best_match is not None:
                new_vertices.append(original_vertices[best_match])
                index_map[best_match] = len(new_vertices) - 1
                sorted_indices.remove(best_match)

        # Process polygons and edges
        polygons = []
        edges = []  # Store edges for colored lines

        mesh = obj.data
        mesh.calc_loop_triangles()

        for poly in mesh.polygons:
            material_index = poly.material_index
            material = obj.material_slots[material_index].material
            if material:
                if material.name.startswith("FE"):  # Handle edges
                    try:
                        edge_color_index = int(material.name[2:])  # Extract color index for edges
                    except ValueError:
                        edge_color_index = 0  # Default to 0 if parsing fails

                    for i in range(len(poly.vertices)):
                        v1 = poly.vertices[i]
                        v2 = poly.vertices[(i + 1) % len(poly.vertices)]
                        edges.append((index_map[v1], index_map[v2], edge_color_index))

                elif material.name.startswith("FX"):  # Handle polygons
                    try:
                        color_index = int(material.name[2:])  # Extract color index for polygons
                    except ValueError:
                        color_index = 0  # Default to 0 if parsing fails

                    poly_vertices = [index_map[vertex] for vertex in poly.vertices]
                    centroid = tuple(
                        sum(mesh.vertices[v].co[i] for v in poly.vertices) / len(poly.vertices)
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



