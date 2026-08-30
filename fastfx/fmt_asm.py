import bpy
import math
import os
from bpy_extras.io_utils import ImportHelper

from .common import hex_to_rgb, distance_from_origin, pair_points_for_compression
from .palette import id_0_c_rgb

# FastFX
# File: fmt_asm.py
# Functions dealing with ASM BSP/GZS import/export.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

# =========================
# ASM BSP/GZS Importer Operator
# =========================
class ImportBSPOperator(bpy.types.Operator, ImportHelper):
    """Import Star Fox ASM BSP/GZS File"""
    bl_idname = "import_mesh.bsp"
    bl_label = "Import Star Fox ASM BSP/GZS File"
    bl_options = {'PRESET', 'UNDO'}

    # Filter to show only asm/bsp files in the file browser
    filter_glob: bpy.props.StringProperty(default="*.asm;*.bsp;*.gzs", options={'HIDDEN'})

    def execute(self, context):
        file_path = self.filepath
        try:
            self.import_bsp(file_path)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import BSP/GZS file: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}

# =========================
# ASM BSP/GZS Importer
# =========================
    def import_bsp(self, file_path):
        points = []
        faces = []
        face_data = []  # Store faces with original order and material indices
        material_map = {}

        is_point_section = False
        is_face_section = False
        invert_x = False

        try:
            with open(file_path, 'r') as f:
                bsp_data = f.read()

            for line in bsp_data.splitlines():
                stripped_line = line.strip()

                # Check if we are entering a points section
                if stripped_line.startswith(("Pointsb", "PointsXb", "Pointsw", "PointsXw")):
                    is_point_section = True
                    is_face_section = False
                    invert_x = stripped_line.startswith("PointsXb") or stripped_line.startswith("PointsXw")
                    continue

                # Check if we are entering a faces section
                # If it starts with "Faces\t", it's a GZS format file
                # If it ends with "Faces", it's a BSP format file
                if stripped_line.endswith("Faces") or stripped_line.startswith("Faces\t"):
                    is_point_section = False
                    is_face_section = True
                    continue

                # Handle points
                # Make sure the shape itself isn't named "Points"
                if is_point_section and stripped_line.startswith("ShapeHdr"):
                    is_point_section = False

                if is_point_section and (stripped_line.startswith("pb") or stripped_line.startswith("pw")):
                    line_without_comments = stripped_line.split(";")[0].strip()
                    if not line_without_comments:
                        continue

                    _, coords = line_without_comments.split("\t", 1)
                    x, y, z = map(int, coords.split(","))

                    # Invert X and Y coordinates
                    x, y = -x, -y

                    points.append((x, -z, y)) # Translate from Star Fox coordinate system to Blender's (Z is up/down)
                    if invert_x:
                        points.append((-x, -z, y)) # Translate from Star Fox coordinate system to Blender's (Z is up/down)

                # Handle faces
                # Make sure the shape itself isn't named "Faces"
                if is_face_section and stripped_line.startswith("ShapeHdr"):
                    is_face_section = False

                if is_face_section and stripped_line.startswith("Face"):
                    parts = stripped_line.split("\t")
                    face_data_str = parts[1]
                    face_parts = face_data_str.split(",")

                    material_index = int(face_parts[0])  # Material index
                    original_face_number = int(face_parts[1])  # Original face number
                    num_points = int(stripped_line[4])  # "FaceX", X = number of points
                    point_indices = list(map(int, face_parts[-num_points:]))

                    material_name = f"FX{material_index}"
                    if material_name not in material_map:
                        material = bpy.data.materials.get(material_name) or bpy.data.materials.new(name=material_name)
                        material.use_nodes = True
                        bsdf = material.node_tree.nodes.get("Principled BSDF")
                        if bsdf:
                            # Convert hex to RGB and set the material's base color
                            hex_color = id_0_c_rgb.get(material_index, "#FFFFFF")  # Default to white
                            linear_rgb_color = hex_to_rgb(hex_color)
                            bsdf.inputs["Base Color"].default_value = linear_rgb_color
                        material_map[material_name] = len(material_map)

                    # Store face data along with its original order
                    face_data.append((original_face_number, tuple(point_indices), material_map[material_name]))

            # Sort faces by their original order
            face_data.sort(key=lambda x: x[0])  # Sort by original_face_number
            faces = [face[1] for face in face_data]  # Extract reordered point indices
            material_indices = [face[2] for face in face_data]  # Extract reordered material indices

            # Create the mesh and object
            mesh_name = os.path.basename(file_path).split('.')[0]
            mesh = bpy.data.meshes.new(mesh_name)
            obj = bpy.data.objects.new(mesh_name, mesh)
            bpy.context.collection.objects.link(obj)

            mesh.from_pydata(points, [], faces)
            mesh.update()

            # Assign materials to the mesh
            for material_name, material_index in material_map.items():
                material = bpy.data.materials.get(material_name)
                if material:
                    mesh.materials.append(material)

            for i, polygon in enumerate(mesh.polygons):
                polygon.material_index = material_indices[i]

            self.report({'INFO'}, f"Mesh '{mesh_name}' created with {len(points)} points and {len(faces)} faces.")
        except Exception as e:
            raise RuntimeError(f"Error processing BSP file: {e}")

# =========================
# GZS/BSP Export Utility functions
# =========================
def calculate_normals_and_viz(vertices, polygons):
    """
    Calculates face normals and generates Viz data.
    Handles division-by-zero issues gracefully.
    """
    viz_data = []
    for poly in polygons:
        indices = poly['indices']
        if len(indices) < 3:
            # SHAPED does not compute normals for edges
            inverted_viz_normal = [0, 0, 0]
            viz_data.append({'indices': indices, 'normal': inverted_viz_normal})
        else:
            v0, v1, v2 = (vertices[i] for i in indices[:3])  # Get the first three vertices

            # Compute face normal using the cross product
            try:
                edge1 = [v1[i] - v0[i] for i in range(3)]
                edge2 = [v2[i] - v0[i] for i in range(3)]
                normal = [
                    edge1[1] * edge2[2] - edge1[2] * edge2[1],
                    edge1[2] * edge2[0] - edge1[0] * edge2[2],
                    edge1[0] * edge2[1] - edge1[1] * edge2[0],
                ]
                # Normalize the vector
                length = math.sqrt(sum(n ** 2 for n in normal))
                normal = [int(n * 127 / length) for n in normal]
                # Invert the normal vector
                inverted_viz_normal = [-n for n in normal]
            except ZeroDivisionError:
                # Set normal to zero if calculation fails
                inverted_viz_normal = [0, 0, 0]

            viz_data.append({'indices': indices, 'normal': inverted_viz_normal})

    return viz_data

def validate_point_format(vertices):
    """
    Determines whether to use Pointsb or Pointsw based on coordinate range.
    """
    max_coord = max(abs(coord) for vertex in vertices for coord in vertex)
    if max_coord > 32767:
        raise ValueError("Point coordinates exceed signed 16-bit range.")
    return 'Pointsb' if max_coord <= 127 else 'Pointsw'

def write_points_section(file, vertices, point_format):
    """
    Writes the Points section (Pointsb or Pointsw) with support for PointsX{format} compression,
    maintaining the original order of chunks in the point list.
    """

    """
    # note that for animated shapes, no compression would be used, if logic for BSP animation were implemented (currently isn't).
    file.write(f"\t{point_format}\t{len(vertices)}\n")
    for i, (x, y, z) in enumerate(vertices):
        x, y, z = round(x), round(y), round(z)
        file.write(f"\tp{point_format[6]}\t{x},{y},{z}\t;{i}\n")
    """

    i = 0
    total_vertices = len(vertices)
    chunk_index = 0

    while i < total_vertices:
        # Check for a compressible pair
        if i + 1 < total_vertices:
            x1, y1, z1 = vertices[i]
            x2, y2, z2 = vertices[i + 1]

            if x1 == -x2 and y1 == y2 and z1 == z2:
                # Start a PointsX{format} chunk
                compressed_chunk = []
                while i + 1 < total_vertices:
                    x1, y1, z1 = vertices[i]
                    x2, y2, z2 = vertices[i + 1]

                    if x1 == -x2 and y1 == y2 and z1 == z2:
                        compressed_chunk.append((x1, y1, z1))
                        i += 2  # Skip the pair
                    else:
                        break

                # Write the compressed chunk
                file.write(f"\tPointsX{point_format[-1]}\t{len(compressed_chunk)}\n")
                for idx, (x, y, z) in enumerate(compressed_chunk):
                    file.write(f"\tp{point_format[6]}\t{int(x)},{int(y)},{int(z)}\t;{chunk_index}\n")
                    chunk_index += 1

                continue

        # If no compressible pair, write an uncompressed chunk
        uncompressed_chunk = []
        while i < total_vertices:
            x1, y1, z1 = vertices[i]
            if i + 1 < total_vertices:
                x2, y2, z2 = vertices[i + 1]
                if x1 == -x2 and y1 == y2 and z1 == z2:
                    break  # Stop before the next compressible pair
            uncompressed_chunk.append((x1, y1, z1))
            i += 1

        # Write the uncompressed chunk
        file.write(f"\t{point_format}\t{len(uncompressed_chunk)}\n")
        for idx, (x, y, z) in enumerate(uncompressed_chunk):
            file.write(f"\tp{point_format[6]}\t{int(x)},{int(y)},{int(z)}\t;{chunk_index}\n")
            chunk_index += 1

def write_faces_section(filepath, file, polygons, viz_data, is_gzs):
    """
    Writes the Vizi and Faces section for BSP or GZS format.
    """

    # Get the shape's name for the point/face ptr labels the ShapeHdr references
    shape_name = os.path.splitext(os.path.basename(filepath))[0]

    # Filter Viz data to exclude entries for 2-pointed faces
    filtered_viz_data = [viz for viz in viz_data if len(viz['indices']) > 2]

    file.write(f"\n{shape_name}_F\n")
    # Create a dummy vizi if there are none, at least one vizi is required for the shape to render
    if len(filtered_viz_data) == 0:
        file.write(f"\tVizis\t1\n")
        file.write(f"\tViz\t0,0,0\t;0\n")
    else:
        file.write(f"\tVizis\t{len(filtered_viz_data)}\n")
        for i, viz in enumerate(filtered_viz_data):
            # We only need to write the first 3 members of indices, see later comment
            indices = ",".join(map(str, viz['indices'][:3]))
            normal = viz['normal']
            normal[2] = -normal[2]  # Invert the Z-component of the normal
            #normal_str = ",".join(map(str, normal))
            #file.write(f"\tViz\t{indices},{normal_str}\t;{i}\n")
            # Turns out the viz macro only stores the first 3 parms to ROM as the faceX macros have the normal too
            # Thanks Pete
            file.write(f"\tViz\t{indices}\t;{i}\n")

    if is_gzs:
        file.write(f"\tFaces\t{len(polygons)}\n")
        for i, poly in enumerate(polygons):
            indices = ",".join(map(str, poly['indices']))
            normal = ",".join(map(str, viz_data[i]['normal']))
            if len(poly['indices']) < 3:
                file.write(f"\tFace{len(poly['indices'])}\t{poly['color_index']},-1,{normal},{indices}\n")
            else:
                file.write(f"\tFace{len(poly['indices'])}\t{poly['color_index']},{i},{normal},{indices}\n")
        file.write("\tFend\n")
    else:
        file.write(f"\n{shape_name}_F1\tFaces\n")
        for i, poly in enumerate(polygons):
            indices = ",".join(map(str, poly['indices']))
            normal = ",".join(map(str, viz_data[i]['normal']))
            if len(poly['indices']) < 3:
                file.write(f"\tFace{len(poly['indices'])}\t{poly['color_index']},-1,{normal},{indices}\n")
            else:
                file.write(f"\tFace{len(poly['indices'])}\t{poly['color_index']},{i},{normal},{indices}\n")
        file.write("\tFend\n")
        # FendQ is only used if the given shape contains a BSP tree
        # TODO figure out BSP trees for BSP format

def _format_shape_hdr_value(value):
    """Round like C's %.0f formatting for a non-negative float."""
    if value >= 0.0:
        return int(math.floor(value + 0.5))
    return int(math.ceil(value - 0.5))


def _shape_header_bounds(vertices):
    """Match SHAPED's C logic: max abs-axis extents and max Euclidean point radius."""
    x_max = 0.0
    y_max = 0.0
    z_max = 0.0
    radius = 0.0

    for x, y, z in vertices:
        ax = abs(x)
        ay = abs(y)
        az = abs(z)

        if ax > x_max:
            x_max = ax
        if ay > y_max:
            y_max = ay
        if az > z_max:
            z_max = az

        point_radius = math.sqrt((x * x) + (y * y) + (z * z))
        if point_radius > radius:
            radius = point_radius

    return x_max, y_max, z_max, radius


def write_shape_header(file, obj, shape_name, vertices, no_simple123=False):
    """
    Writes the ShapeHdr line based on the bounding box.
    """

    # Format of the Shape header is as follows:
    # ShapeHdr  pointptr,bank,faceptr,0,sortz,0,0,scale,colboxptr,xmax,ymax,zmax,radius,colptr,shadowptr,simple1ptr,simple2ptr,simple3ptr,<Name>

    # Simplified Shape header is as follows:
    # ShapeHdr  pointptr,bank,faceptr,0,sortz,0,0,scale,colboxptr,xmax,ymax,zmax,radius,colptr,shadowptr,<Name>

    # Get ShapeHdr properties from object

    zsort_priority = obj.get("zsort_priority", "0")
    scale = obj.get("scale", "0")
    colbox_label = obj.get("colbox_label", "0")
    color_palette = obj.get("color_palette", "id_0_c")
    shadow_shape = obj.get("shadow_shape", "0")
    close_lod_shape = obj.get("close_lod_shape", "0")
    mid_lod_shape = obj.get("mid_lod_shape", "0")
    far_lod_shape = obj.get("far_lod_shape", "0")

    x_max, y_max, z_max, radius = _shape_header_bounds(vertices)
    x_max_i = _format_shape_hdr_value(x_max)
    y_max_i = _format_shape_hdr_value(y_max)
    z_max_i = _format_shape_hdr_value(z_max)
    radius_i = _format_shape_hdr_value(radius)

    file.write(f"\tifne\tDO_HDR\n\n")
    file.write(f"{shape_name}\n")
    if not no_simple123:
        file.write(
            f"\tShapeHdr\t" \
            f"{shape_name}_P,0,{shape_name}_F,0,{zsort_priority},0,0,{scale},{colbox_label}," \
            f"{x_max_i},{y_max_i},{z_max_i},{radius_i}," \
            f"{color_palette},{shadow_shape},{close_lod_shape},{mid_lod_shape},{far_lod_shape},<{shape_name}>\n"
    )
    else:
        file.write(
            f"\tShapeHdr\t" \
            f"{shape_name}_P,0,{shape_name}_F,0,{zsort_priority},0,0,{scale},{colbox_label}," \
            f"{x_max_i},{y_max_i},{z_max_i},{radius_i}," \
            f"{color_palette},{shadow_shape},<{shape_name}>\n"
    )
    file.write("\telseif\n")

def collect_data_from_mesh(obj, sort_mode="distance", compress_point_pairs=True):
    """
    Extracts vertices and polygons (including edges for FE# materials) from a Blender object,
    optionally optimizing points for compression.

    :param obj: Blender mesh object to export.
    :param sort_mode: Sorting mode ("distance", "material", "none").
    :param compress_point_pairs: Whether to reorder vertices into compression-friendly pairs.
    """
    # Translate from Blender's coordinate system to Star Fox's: Invert all, swap Y/Z
    original_vertices = [(-(v.co.x), -(v.co.z), -(v.co.y)) for v in obj.data.vertices]

    if compress_point_pairs:
        new_vertices, index_map = pair_points_for_compression(original_vertices, prefer_closest_fallback=True)
    else:
        new_vertices = list(original_vertices)
        index_map = {i: i for i in range(len(original_vertices))}

    # Extract polygons and remap indices
    polygons = []
    # Track seen edge positions (position pairs + color) to avoid duplicates when creating 2-point faces
    seen_edges = set()
    for poly in obj.data.polygons:
        indices = [index_map[vertex] for vertex in poly.vertices]
        material_index = poly.material_index
        material_name = obj.data.materials[material_index].name if material_index < len(obj.data.materials) else "FX0"

        if material_name.startswith("FE"):
            # If the material indicates edges, create 2-pointed faces for each edge
            try:
                color_index = int(material_name[2:])
            except ValueError:
                color_index = 0  # Default to 0 if parsing fails

            # Convert the polygon into edges, skipping duplicate edges located at the same positions
            for i in range(len(indices)):
                a = indices[i]
                b = indices[(i + 1) % len(indices)]  # Wrap around for closed edges

                # Use the endpoint positions (rounded) and color index as the dedupe key
                pa = tuple(round(c, 6) for c in new_vertices[a])
                pb = tuple(round(c, 6) for c in new_vertices[b])
                key = (pa, pb) if pa <= pb else (pb, pa)
                key = (key, color_index)

                if key in seen_edges:
                    continue
                seen_edges.add(key)

                midpoint = tuple((new_vertices[a][j] + new_vertices[b][j]) / 2 for j in range(3))
                polygons.append({'indices': [a, b], 'color_index': color_index, 'distance': distance_from_origin(midpoint)})

        else:
            # Handle standard polygons
            try:
                color_index = int(material_name[2:]) if material_name.startswith("FX") else 0
            except ValueError:
                color_index = 0  # Default to 0 if parsing fails

            # Calculate centroid
            centroid = tuple(
                sum(new_vertices[vertex][i] for vertex in indices) / len(indices) for i in range(3)
            )
            polygons.append({'indices': indices, 'color_index': color_index, 'distance': distance_from_origin(centroid)})

    # Apply sorting based on the selected mode
    if sort_mode == "distance":
        polygons.sort(key=lambda p: p['distance'], reverse=True)  # Sort by distance from origin (farthest last)
    elif sort_mode == "material":
        polygons.sort(key=lambda p: p['color_index'])  # Sort by material index (seems to be broken)
#    elif sort_mode == "material":
        # Create a mapping of material names to their slot index
#        material_slot_order = {mat.name: idx for idx, mat in enumerate(obj.data.materials)}
#        polygons.sort(key=lambda p: material_slot_order.get(obj.material_slots[p[3]].material.name, 9999))

    # If sort_mode is "none," no sorting is applied

    return new_vertices, polygons


def export_to_format(filepath, obj, sort_mode, is_gzs, no_simple123, compress_point_pairs=True):
    """
    Main export function for BSP/GZS format.
    """
    shape_name = os.path.splitext(os.path.basename(filepath))[0]
    vertices, polygons = collect_data_from_mesh(obj, sort_mode, compress_point_pairs)
    point_format = validate_point_format(vertices)
    viz_data = calculate_normals_and_viz(vertices, polygons)

    with open(filepath, "w") as file:
        if is_gzs:
            file.write(f";--Shape file ----- {shape_name}.gzs ---- Generated with FastFX\n")
        else:
            file.write(f";--Shape file ----- {shape_name}.bsp ---- Generated with FastFX\n")
        write_shape_header(file, obj, shape_name, vertices, no_simple123)
        file.write(f"{shape_name}_P\n")
        write_points_section(file, vertices, point_format)
        file.write("\n\tEndPoints")
        write_faces_section(filepath, file, polygons, viz_data, is_gzs)
        file.write("\tEndShape\n\n\tendc\n")

# =========================
# ASM BSP Export Operator
# =========================
class ExportToBSP(bpy.types.Operator):
    """Export to BSP Format"""
    bl_idname = "export_mesh.bsp"
    bl_label = "Export Treeless ASM BSP"
    bl_options = {'PRESET'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    sort_mode: bpy.props.EnumProperty(
        name="Sort Mode",
        description="Choose how to sort faces and edges in the exported file",
        items=[
            ('distance', "Distance from Origin", "Sort by distance from the origin"),
            ('material', "Material Order", "Sort by material order. Last material is drawn first"),
            ('none', "No Sorting", "No sorting; use Blender's internal order")
        ],
        default='distance'
    )
    no_simple123: bpy.props.BoolProperty(
        name="Simplified ShapeHdr",
        description="Exclude LODs from the shape header when enabled",
        default=False
    )
    compress_point_pairs: bpy.props.BoolProperty(
        name="Compress point pairs",
        description="Pair vertices for compact format compression during export",
        default=True
    )

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object.")
            return {'CANCELLED'}
        export_to_format(self.filepath, obj, self.sort_mode, False, self.no_simple123, self.compress_point_pairs)
        self.report({'INFO'}, f"Exported to BSP: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.label(text="ASM BSP Export Options", icon='INFO')
        layout.prop(self, "sort_mode", text="Sort Mode")
        layout.prop(self, "no_simple123", text="Simplified ShapeHdr")
        layout.prop(self, "compress_point_pairs", text="Compress point pairs")

# =========================
# ASM GZS Export Operator
# =========================
class ExportToGZS(bpy.types.Operator):
    """Export to GZS Format"""
    bl_idname = "export_mesh.gzs"
    bl_label = "Export ASM GZS"
    bl_options = {'PRESET'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    sort_mode: bpy.props.EnumProperty(
        name="Sort Mode",
        description="Choose how to sort faces and edges in the exported file",
        items=[
            ('distance', "Distance from Origin", "Sort by distance from the origin"),
            ('material', "Material Order", "Sort by material order. Last material is drawn first"),
            ('none', "No Sorting", "No sorting; use Blender's internal order")
        ],
        default='distance'
    )
    no_simple123: bpy.props.BoolProperty(
        name="Simplified ShapeHdr",
        description="Exclude LODs from the shape header when enabled",
        default=False
    )
    compress_point_pairs: bpy.props.BoolProperty(
        name="Compress point pairs",
        description="Pair vertices for compact format compression during export",
        default=True
    )

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object.")
            return {'CANCELLED'}
        export_to_format(self.filepath, obj, self.sort_mode, True, self.no_simple123, self.compress_point_pairs)
        self.report({'INFO'}, f"Exported to GZS: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.label(text="ASM GZS Export Options", icon='INFO')
        layout.prop(self, "sort_mode", text="Sort Mode")
        layout.prop(self, "no_simple123", text="Simplified ShapeHdr")
        layout.prop(self, "compress_point_pairs", text="Compress point pairs")

