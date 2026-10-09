import bpy
import os
import re

from .common import hex_to_rgb
from .animation import (
    animation_frame_coordinates,
    animation_frame_count,
    create_animation_object,
    is_vertex_animation,
)
from .palette import id_0_c_rgb

# FastFX
# File: fmt_3dan.py
# Functions dealing with animated Fundoshi-Kun format import/export.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

# =========================
# 3DAN Importer
# =========================
class Import3DANOperator(bpy.types.Operator):
    """Import 3DAN/3DGI File"""
    bl_idname = "import_mesh.3dan"
    bl_label = "Import 3DAN/3DGI File"
    bl_options = {'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    # Filter to show only supported files in the file browser
    filter_glob: bpy.props.StringProperty(default="*.anm", options={'HIDDEN'})

    def execute(self, context):
        self.import_3dan(self.filepath, context)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def import_3dan(self, filepath, context):
        # Extract the base name of the file (without extension) to use as object and mesh name
        base_name = os.path.splitext(os.path.basename(filepath))[0]

        with open(filepath, 'r') as file:
            lines = file.readlines()
        
        if not lines[0].strip() in {"3DAN", "3DGI"}:
            self.report({'ERROR'}, "Invalid file format")
            return
        else:
            is_animated = True

        point_count = int(lines[1].strip())
        frame_count = int(lines[2].strip()) if is_animated else 1
        
        # Parse points
        points = [[] for _ in range(frame_count)]
        index = 3
        for frame in range(frame_count):
            for _ in range(point_count):
                x, y, z = map(int, lines[index].strip().split())
                points[frame].append((x, -z, y)) # Translate from 3DG1/3DAN coordinate system to Blender's (Z is up/down)
                index += 1

        # Parse polygons
        polygons = []
        while index < len(lines):
            line = lines[index].strip()
            if not line:
                index += 1
                continue
            if line == chr(0x1A):  # EOF marker
                break
            parts = list(map(int, line.split()))
            npoints = parts[0]
            poly_points = parts[1:npoints+1]
            color_index = parts[npoints+1]
            polygons.append((poly_points, color_index))
            index += 1
        
        polygons_data = [poly[0] for poly in polygons]
        if frame_count > 1 and not context.scene.fastfx_use_legacy_animation_objects:
            objects = [
                create_animation_object(context, base_name, points, polygons_data)
            ]
        else:
            objects = []
            for frame, frame_points in enumerate(points):
                frame_name = (
                    f"{base_name}_frame{frame}"
                    if frame_count > 1
                    else base_name
                )
                mesh = bpy.data.meshes.new(frame_name)
                mesh.from_pydata(frame_points, [], polygons_data)
                mesh.update()
                obj = bpy.data.objects.new(frame_name, mesh)
                context.collection.objects.link(obj)
                objects.append(obj)

        # Assign colors and materials to imported mesh objects.
        for obj in objects:
            for poly, (_, color_index) in zip(obj.data.polygons, polygons):
                mat_name = f"FX{color_index}"
                material = bpy.data.materials.get(mat_name) or bpy.data.materials.new(name=mat_name)
                material.use_nodes = True
                bsdf = material.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    hex_color = id_0_c_rgb.get(color_index, "#FFFFFF")
                    bsdf.inputs["Base Color"].default_value = hex_to_rgb(hex_color)
                if obj.data.materials.find(material.name) == -1:
                    obj.data.materials.append(material)
                poly.material_index = obj.data.materials.find(material.name)


        self.report({'INFO'}, "3DAN file imported successfully")

# =========================
# 3DAN Exporter
# =========================
def _object_name_sort_key(obj):
    """Sort object names naturally so numbered animation frames stay in order."""
    name_parts = re.split(r"(\d+)", obj.name.casefold())
    natural_name = tuple(
        (1, int(part)) if part.isdigit() else (0, part)
        for part in name_parts
    )
    return natural_name, obj.name


def sort_animation_objects(objects):
    """Return animation frame objects in natural object-name order."""
    return sorted(objects, key=_object_name_sort_key)


def write_3dan(filepath, objects, frame_number, validate_signed_16bit=False):
    """
    Writes the 3DAN file format.

    :param filepath: The output file path.
    :param objects: List of Blender objects (with meshes) representing animation frames.
    :param frame_number: Total number of frames.
    :param validate_signed_16bit: Reject points outside SHAPED's signed 16-bit coordinate range.
    """
    # Sort object names naturally so Frame2 comes before Frame10.
    animated_object = (
        objects[0]
        if len(objects) == 1 and is_vertex_animation(objects[0])
        else None
    )
    if animated_object is not None:
        sorted_objects = [animated_object]
        frame_number = animation_frame_count(animated_object)
    else:
        sorted_objects = sort_animation_objects(objects)

    if not sorted_objects:
        raise ValueError("No mesh objects found for animation export.")

    if validate_signed_16bit:
        for frame_index, obj in enumerate(sorted_objects[:frame_number]):
            coordinates = (
                animation_frame_coordinates(animated_object, frame_index)
                if animated_object is not None
                else [vertex.co for vertex in obj.data.vertices]
            )
            for point_index, coordinate in enumerate(coordinates):
                x, y, z = (int(round(value)) for value in coordinate)
                for axis, coordinate in (("x", x), ("y", z), ("z", -y)):
                    if not -32768 <= coordinate <= 32767:
                        raise ValueError(
                            f"Frame '{obj.name}' point {point_index} {axis} coordinate {coordinate} "
                            "is outside the signed 16-bit range (-32768 to 32767)."
                        )

    with open(filepath, "w") as f:
        # Header
        f.write("3DAN\n")
        f.write(f"{len(sorted_objects[0].data.vertices)}\n")  # Total unique points (assume consistent vertex count)
        f.write(f"{frame_number}\n")  # Number of animation frames

        # Write point data per frame
        for frame_index in range(frame_number):
            if animated_object is not None:
                coordinates = animation_frame_coordinates(animated_object, frame_index)
            else:
                coordinates = [vertex.co for vertex in sorted_objects[frame_index].data.vertices]
            for coordinate in coordinates:
                # Convert vertex coordinates to integers
                x, y, z = (int(round(value)) for value in coordinate)
                f.write(f"{x} {z} {-(y)}\n")  # Translate back to the 3DG1/3DAN coordinate system (Y is up/down)

        # Write polygon data (from the first frame's mesh)
        base_mesh = sorted_objects[0].data
        for poly in base_mesh.polygons:
            npoints = len(poly.vertices)
            f.write(f"{npoints} ")
            f.write(" ".join(map(str, poly.vertices)))

            # Extract color index from material name (if it follows FX# format)
            mat_index = poly.material_index
            material = base_mesh.materials[mat_index] if mat_index < len(base_mesh.materials) else None
            color_index = 0  # Default color index if no material is found or improperly named
            if material and material.name.startswith("FX"):
                try:
                    color_index = int(material.name[2:])  # Extract number after 'FX'
                except ValueError:
                    pass  # Leave color_index as 0 if extraction fails

            f.write(f" {color_index}\n")

        # End marker (0x1a character)
        f.write(chr(0x1a))

# =========================
# 3DAN Export Operator
# =========================
class Export3DAN(bpy.types.Operator):
    """Export to 3DAN Format"""
    bl_idname = "export_scene.3dan"
    bl_label = "Export 3DAN"
    bl_options = {'PRESET'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    filter_glob: bpy.props.StringProperty(default="*.anm", options={'HIDDEN'})

    def execute(self, context):
        filepath = self.filepath
        if context.scene.fastfx_use_legacy_animation_objects:
            frame_objects = [
                obj for obj in context.scene.objects if obj.type == "MESH"
            ]
            frame_number = len(frame_objects)
            if not frame_objects:
                self.report({'ERROR'}, "No objects found for export.")
                return {'CANCELLED'}
        else:
            obj = context.active_object
            if not is_vertex_animation(obj):
                self.report({'ERROR'}, "Select an animated mesh object.")
                return {'CANCELLED'}
            frame_objects = [obj]
            frame_number = animation_frame_count(obj)

        try:
            write_3dan(filepath, frame_objects, frame_number)
        except (OSError, ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, f"Failed to export 3DAN: {exc}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {frame_number} frames to {filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
