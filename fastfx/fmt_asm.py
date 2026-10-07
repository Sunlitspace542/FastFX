import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
from bpy_extras.io_utils import ImportHelper

from .common import hex_to_rgb
from .fmt_3dan import sort_animation_objects, write_3dan
from .fmt_3dg1 import write_3dg1
from .palette import id_0_c_rgb
from .shaped import ShapeHeader, load as load_shape, write as write_shape

# FastFX
# File: fmt_asm.py
# Functions dealing with ASM BSP/GZS import/export.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

_POINT_DIRECTIVE = re.compile(r"\b(PointsX?[bw])\s+(\d+)", re.IGNORECASE)
_POINT_VALUE = re.compile(r"\bp[bw]\s+(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)", re.IGNORECASE)


def _asm_symbol_name(name):
    """Return a valid assembler symbol for the ShapeHdr name."""
    sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", str(name))
    if not sanitized:
        sanitized = "S"
    if sanitized[0].isdigit():
        sanitized = f"_{sanitized}"
    return sanitized


def _parse_point_macro(lines, line_index, next_point_index):
    """Read one Points/PointsX block and return decoded points and next line."""
    directive_line = lines[line_index].split(";", 1)[0]
    match = _POINT_DIRECTIVE.search(directive_line)
    if not match:
        return {}, line_index + 1, next_point_index

    mirrored = match.group(1).lower().startswith("pointsx")
    point_rows = int(match.group(2))
    points = {}
    cursor = line_index + 1
    for _ in range(point_rows):
        while cursor < len(lines) and not _POINT_VALUE.search(lines[cursor].split(";", 1)[0]):
            if _POINT_DIRECTIVE.search(lines[cursor].split(";", 1)[0]):
                raise ValueError("Point block ended before all coordinates were read.")
            cursor += 1
        if cursor >= len(lines):
            raise ValueError("Point block ended before all coordinates were read.")

        row = lines[cursor]
        value_match = _POINT_VALUE.search(row.split(";", 1)[0])
        x, y, z = map(int, value_match.groups())
        point_index = next_point_index

        # Convert Star Fox coordinates to Blender coordinates.
        points[point_index] = (-x, -z, -y)
        if mirrored:
            points[point_index + 1] = (x, -z, -y)
        next_point_index = max(next_point_index, point_index + (2 if mirrored else 1))
        cursor += 1

    return points, cursor, next_point_index


def _parse_asm_points(lines):
    """Decode static and SHAPED animated point blocks into Blender-space frames."""
    static_points = {}
    animated_blocks = []
    next_point_index = 0
    cursor = 0

    while cursor < len(lines):
        content = lines[cursor].split(";", 1)[0].strip()
        if content.lower().startswith("endpoints"):
            break

        frames_match = re.match(r"Frames\s+(\d+)\b", content, re.IGNORECASE)
        if frames_match:
            frame_count = int(frames_match.group(1))
            if frame_count < 1:
                raise ValueError("Animated point blocks must contain at least one frame.")

            jump_targets = []
            cursor += 1
            while cursor < len(lines):
                target_match = re.match(r"jumptab\s+([.\w]+)", lines[cursor].split(";", 1)[0].strip(), re.IGNORECASE)
                if not target_match:
                    break
                jump_targets.append(target_match.group(1))
                cursor += 1
            if len(jump_targets) != frame_count:
                raise ValueError(
                    f"Animated point block declares {frame_count} frames but has "
                    f"{len(jump_targets)} jump-table entries."
                )

            block_frames = []
            block_next_point_index = next_point_index
            for target in jump_targets:
                label_pattern = re.compile(rf"^\s*{re.escape(target)}(?:\s|$)", re.IGNORECASE)
                while cursor < len(lines) and not label_pattern.match(lines[cursor].split(";", 1)[0]):
                    cursor += 1
                if cursor >= len(lines):
                    raise ValueError(f"Animated frame label {target} was not found.")

                frame_points = {}
                frame_next_point_index = next_point_index
                while cursor < len(lines):
                    content = lines[cursor].split(";", 1)[0].strip()
                    if re.match(r"jump\s+\.EB[\w]*\b", content, re.IGNORECASE):
                        cursor += 1
                        break
                    if re.match(r"\.EB[\w]*\b", content, re.IGNORECASE):
                        cursor += 1
                        break
                    directive_match = _POINT_DIRECTIVE.search(content)
                    if directive_match:
                        points, cursor, frame_next_point_index = _parse_point_macro(
                            lines, cursor, frame_next_point_index
                        )
                        frame_points.update(points)
                    else:
                        cursor += 1
                block_frames.append(frame_points)
                if block_frames:
                    block_next_point_index = max(block_next_point_index, frame_next_point_index)
            next_point_index = block_next_point_index

            # The final frame may jump to the shared end label rather than
            # ending directly at it.
            while cursor < len(lines):
                content = lines[cursor].split(";", 1)[0].strip()
                if re.match(r"\.EB[\w]*\b", content, re.IGNORECASE):
                    cursor += 1
                    break
                if content and not content.lower().startswith(("jump ",)):
                    break
                cursor += 1
            animated_blocks.append(block_frames)
            continue

        if _POINT_DIRECTIVE.search(content):
            points, cursor, next_point_index = _parse_point_macro(lines, cursor, next_point_index)
            static_points.update(points)
        else:
            cursor += 1

    if not animated_blocks:
        return [[static_points[index] for index in range(max(static_points, default=-1) + 1)]]

    frame_count = len(animated_blocks[0])
    if any(len(block) != frame_count for block in animated_blocks):
        raise ValueError("Animated point blocks declare different frame counts.")

    frames = []
    point_count = max(
        (max(points, default=-1) for block in animated_blocks for points in block),
        default=-1,
    )
    point_count = max(point_count, max(static_points, default=-1)) + 1
    for frame_index in range(frame_count):
        frame_points = dict(static_points)
        for block in animated_blocks:
            frame_points.update(block[frame_index])
        missing = [index for index in range(point_count) if index not in frame_points]
        if missing:
            raise ValueError(f"Point data is missing index {missing[0]} in animation frame {frame_index}.")
        frames.append([frame_points[index] for index in range(point_count)])
    return frames

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
        faces = []
        face_data = []  # Store faces with original order and material indices
        material_map = {}

        is_face_section = False

        try:
            with open(file_path, 'r') as f:
                bsp_data = f.read()

            file_lines = bsp_data.splitlines()
            points_by_frame = _parse_asm_points(file_lines)

            for line in file_lines:
                stripped_line = line.strip()

                # Check if we are entering a faces section
                # If it starts with "Faces\t", it's a GZS format file
                # If it ends with "Faces", it's a BSP format file
                if stripped_line.endswith("Faces") or stripped_line.startswith("Faces\t"):
                    is_face_section = True
                    continue

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

            # Create a mesh object for each animation frame, matching the
            # separate-frame-object convention used by the 3DAN importer.
            mesh_name = os.path.basename(file_path).split('.')[0]
            for frame_index, frame_points in enumerate(points_by_frame):
                object_name = mesh_name if len(points_by_frame) == 1 else f"{mesh_name}_Frame{frame_index}"
                mesh = bpy.data.meshes.new(object_name)
                obj = bpy.data.objects.new(object_name, mesh)
                bpy.context.collection.objects.link(obj)

                mesh.from_pydata(frame_points, [], faces)
                mesh.update()

                # Assign materials to the mesh
                for material_name, material_index in material_map.items():
                    material = bpy.data.materials.get(material_name)
                    if material:
                        mesh.materials.append(material)

                for i, polygon in enumerate(mesh.polygons):
                    polygon.material_index = material_indices[i]

            self.report(
                {'INFO'},
                f"Mesh '{mesh_name}' created with {len(points_by_frame)} frame(s), "
                f"{len(points_by_frame[0])} points and {len(faces)} faces."
            )
        except Exception as e:
            raise RuntimeError(f"Error processing BSP file: {e}")


def export_to_format(filepath, obj, sort_mode, output_format, no_simple123, compress_point_pairs=True, tree=True):
    """Export a Blender mesh through a temporary 3DG1 file and the SHAPED compiler."""
    output_path = Path(filepath)
    shape_name = _asm_symbol_name(obj.get("assembly_name") or output_path.stem)

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


def export_animated_to_format(filepath, objects, output_format, no_simple123, tree=True):
    """Export animation frame objects through a temporary 3DAN file and SHAPED."""
    output_path = Path(filepath)
    frame_objects = sort_animation_objects(objects)
    if not frame_objects:
        raise ValueError("No mesh objects found for animation export.")
    base_object = frame_objects[0]
    shape_name = _asm_symbol_name(base_object.get("assembly_name") or output_path.stem)

    first_mesh = frame_objects[0].data
    vertex_count = len(first_mesh.vertices)
    topology = tuple(tuple(polygon.vertices) for polygon in first_mesh.polygons)
    for obj in frame_objects:
        mesh = obj.data
        if len(mesh.vertices) != vertex_count:
            raise ValueError(
                f"Frame '{obj.name}' has {len(mesh.vertices)} vertices; expected {vertex_count}."
            )
        if tuple(tuple(polygon.vertices) for polygon in mesh.polygons) != topology:
            raise ValueError(f"Frame '{obj.name}' has different face topology from frame '{frame_objects[0].name}'.")

    with TemporaryDirectory() as temporary:
        source_path = Path(temporary) / "animation.3dan"
        write_3dan(source_path, frame_objects, len(frame_objects), validate_signed_16bit=True)
        shape = load_shape(source_path)
        shape.header = ShapeHeader(
            name=shape_name,
            zsort_priority=base_object.get("zsort_priority", "0"),
            scale=base_object.get("scale", "0"),
            colbox=base_object.get("colbox_label", "0"),
            colour_table=base_object.get("color_palette", "id_0_c"),
            shadow=base_object.get("shadow_shape", "0"),
            simple1=base_object.get("close_lod_shape", "0"),
            simple2=base_object.get("mid_lod_shape", "0"),
            simple3=base_object.get("far_lod_shape", "0"),
            simplified=no_simple123,
        )

        if output_format == "bsp":
            write_shape(shape, output_path, "bsp", tree=tree)
        elif output_format == "gzs":
            write_shape(shape, output_path, "gzs")
        else:
            raise ValueError(f"Unsupported animated ASM export format: {output_format}")


# =========================
# ASM BSP Export Operators
# =========================
class ExportToBSP(bpy.types.Operator):
    """Export to Star Fox ASM BSP Format"""
    bl_idname = "export_mesh.bsp"
    bl_label = "Export ASM BSP"
    bl_options = {'PRESET'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    def execute(self, context):
        obj = context.object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object.")
            return {'CANCELLED'}
        try:
            scene = context.scene
            export_to_format(
                self.filepath,
                obj,
                scene.fastfx_export_sort_mode,
                "bsp",
                scene.fastfx_export_simplified_shapehdr,
                scene.fastfx_export_compress_point_pairs,
                tree=True,
            )
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to export BSP: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Exported BSP with tree to: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class ExportToBSPTreeless(bpy.types.Operator):
    """Export to Star Fox ASM BSP Format without a BSP tree"""
    bl_idname = "export_mesh.bsp_treeless"
    bl_label = "Export Treeless ASM BSP"
    bl_options = {'PRESET'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    def execute(self, context):
        obj = context.object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object.")
            return {'CANCELLED'}
        try:
            scene = context.scene
            export_to_format(
                self.filepath,
                obj,
                scene.fastfx_export_sort_mode,
                "bsp",
                scene.fastfx_export_simplified_shapehdr,
                scene.fastfx_export_compress_point_pairs,
                tree=False,
            )
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to export treeless BSP: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Exported treeless BSP to: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# =========================
# ASM GZS Export Operator
# =========================
class ExportToGZS(bpy.types.Operator):
    """Export to Star Fox ASM GZS Format"""
    bl_idname = "export_mesh.gzs"
    bl_label = "Export ASM GZS"
    bl_options = {'PRESET'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    def execute(self, context):
        obj = context.object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object.")
            return {'CANCELLED'}
        try:
            scene = context.scene
            export_to_format(
                self.filepath,
                obj,
                scene.fastfx_export_sort_mode,
                "gzs",
                scene.fastfx_export_simplified_shapehdr,
                scene.fastfx_export_compress_point_pairs,
            )
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to export GZS: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Exported to GZS: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class ExportAnimatedToASM(bpy.types.Operator):
    """Export animated mesh objects to Star Fox ASM through SHAPED."""
    bl_idname = "export_mesh.animated_asm"
    bl_label = "Export Animated ASM"
    bl_options = {'PRESET'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.asm;*.bsp;*.gzs", options={'HIDDEN'})
    output_format: bpy.props.EnumProperty(
        items=[
            ('bsp', "BSP", "Compile animation as BSP with a tree"),
            ('bsp_treeless', "BSP (treeless)", "Compile animation as a flat BSP face list"),
            ('gzs', "GZS", "Compile animation as GZS"),
        ],
        default='bsp',
        options={'HIDDEN'},
    )
    def execute(self, context):
        frame_objects = [obj for obj in context.scene.objects if obj.type == "MESH"]
        if not frame_objects:
            self.report({'ERROR'}, "No mesh objects found for animation export.")
            return {'CANCELLED'}

        output_format = "gzs" if self.output_format == "gzs" else "bsp"
        tree = self.output_format == "bsp"
        try:
            export_animated_to_format(
                self.filepath,
                frame_objects,
                output_format,
                context.scene.fastfx_export_simplified_shapehdr,
                tree=tree,
            )
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to export animated {self.output_format.upper()}: {exc}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported animated {self.output_format.upper()} to: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
