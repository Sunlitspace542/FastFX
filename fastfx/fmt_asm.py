import os
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
from bpy_extras.io_utils import ImportHelper

from .common import hex_to_rgb
from .fmt_3dg1 import write_3dg1
from .palette import id_0_c_rgb
from .shaped import ShapeHeader, load as load_shape, write as write_shape

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


def export_to_format(filepath, obj, sort_mode, output_format, no_simple123, compress_point_pairs=True, tree=True):
    """Export a Blender mesh through a temporary 3DG1 file and the SHAPED compiler."""
    output_path = Path(filepath)
    shape_name = output_path.stem

    # Format of the Shape header is as follows:
    # ShapeHdr  pointptr,bank,faceptr,0,sortz,0,0,scale,colboxptr,xmax,ymax,zmax,radius,colptr,shadowptr,simple1ptr,simple2ptr,simple3ptr,<Name>

    # Simplified Shape header is as follows:
    # ShapeHdr  pointptr,bank,faceptr,0,sortz,0,0,scale,colboxptr,xmax,ymax,zmax,radius,colptr,shadowptr,<Name>

    with TemporaryDirectory() as temporary:
        source_path = Path(temporary) / "model.3dg1"
        write_3dg1(source_path, obj, sort_mode, compress_point_pairs, validate_signed_16bit=True)
        shape = load_shape(source_path)
        shape.header = ShapeHeader(
            name=shape_name,
            zsort_priority=obj.get("zsort_priority", "0"),
            scale=obj.get("scale", "0"),
            colbox=obj.get("colbox_label", "0"),
            colour_table=obj.get("color_palette", "id_0_c"),
            shadow=obj.get("shadow_shape", "0"),
            simple1=obj.get("close_lod_shape", "0"),
            simple2=obj.get("mid_lod_shape", "0"),
            simple3=obj.get("far_lod_shape", "0"),
            simplified=no_simple123,
        )

        if output_format == "bsp":
            write_shape(shape, output_path, "bsp", tree=tree)
        elif output_format == "gzs":
            write_shape(shape, output_path, "gzs")
        else:
            raise ValueError(f"Unsupported ASM export format: {output_format}")


# =========================
# ASM BSP Export Operators
# =========================
class ExportToBSP(bpy.types.Operator):
    """Export to Star Fox ASM BSP Format"""
    bl_idname = "export_mesh.bsp"
    bl_label = "Export ASM BSP"
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
        try:
            export_to_format(self.filepath, obj, self.sort_mode, "bsp", self.no_simple123, self.compress_point_pairs, tree=True)
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to export BSP: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Exported BSP with tree to: {self.filepath}")
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


class ExportToBSPTreeless(bpy.types.Operator):
    """Export to Star Fox ASM BSP Format without a BSP tree"""
    bl_idname = "export_mesh.bsp_treeless"
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
        try:
            export_to_format(self.filepath, obj, self.sort_mode, "bsp", self.no_simple123, self.compress_point_pairs, tree=False)
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to export treeless BSP: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Exported treeless BSP to: {self.filepath}")
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
    """Export to Star Fox ASM GZS Format"""
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
        try:
            export_to_format(self.filepath, obj, self.sort_mode, "gzs", self.no_simple123, self.compress_point_pairs)
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to export GZS: {exc}")
            return {'CANCELLED'}
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
