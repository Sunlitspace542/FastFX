import bpy
import os

from .common import hex_to_rgb
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
                continue
            if line == chr(0x1A):  # EOF marker
                break
            parts = list(map(int, line.split()))
            npoints = parts[0]
            poly_points = parts[1:npoints+1]
            color_index = parts[npoints+1]
            polygons.append((poly_points, color_index))
            index += 1
        
        # Create Blender objects
        for frame, frame_points in enumerate(points):
            mesh = bpy.data.meshes.new(f"Frame{frame}")
            obj = bpy.data.objects.new(f"Frame{frame}", mesh)
            context.collection.objects.link(obj)

            mesh.from_pydata(frame_points, [], [poly[0] for poly in polygons])
            mesh.update()

            # Assign colors as materials
            for poly, (_, color_index) in zip(mesh.polygons, polygons):
                # Create a material name based on the color index
                mat_name = f"FX{color_index}"
                
                # Check if the material already exists; otherwise, create it
                material = bpy.data.materials.get(mat_name) or bpy.data.materials.new(name=mat_name)
                material.use_nodes = True  # Enable nodes to customize material properties
                
                # Access the Principled BSDF node and set the material color
                bsdf = material.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    hex_color = id_0_c_rgb.get(color_index, "#FFFFFF")  # Use a default color (white) if index is not mapped
                    linear_rgb_color = hex_to_rgb(hex_color)  # Convert the hex color to linear RGB
                    bsdf.inputs["Base Color"].default_value = linear_rgb_color  # Set color with alpha
                
                # Append the material to the mesh object
                if obj.data.materials.find(material.name) == -1:
                    obj.data.materials.append(material)
                
                # Assign the material to the polygon
                poly.material_index = obj.data.materials.find(material.name)


        self.report({'INFO'}, "3DAN file imported successfully")

# =========================
# 3DAN Exporter
# =========================
def write_3dan(filepath, objects, frame_number):
    """
    Writes the 3DAN file format.

    :param filepath: The output file path.
    :param objects: List of Blender objects (with meshes) representing animation frames.
    :param frame_number: Total number of frames.
    """
    # Sort objects by name to ensure frames are in the correct order
    sorted_objects = sorted(objects, key=lambda obj: obj.name)

    with open(filepath, "w") as f:
        # Header
        f.write("3DAN\n")
        f.write(f"{len(sorted_objects[0].data.vertices)}\n")  # Total unique points (assume consistent vertex count)
        f.write(f"{frame_number}\n")  # Number of animation frames

        # Write point data per frame
        for frame_index in range(frame_number):
            mesh = sorted_objects[frame_index].data
            for vertex in mesh.vertices:
                # Convert vertex coordinates to integers
                x, y, z = (int(round(coord)) for coord in vertex.co)
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
        objects = context.scene.objects

        # Collect objects for frames
        frame_objects = [obj for obj in objects if obj.type == "MESH"]

        if len(frame_objects) < 1:
            self.report({'ERROR'}, "No objects found for export.")
            return {'CANCELLED'}

        # Assume the number of objects corresponds to the number of frames
        frame_number = len(frame_objects)

        # Export to 3DAN
        write_3dan(filepath, frame_objects, frame_number)

        self.report({'INFO'}, f"Exported {frame_number} frames to {filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

