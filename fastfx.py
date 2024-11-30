import bpy
import bmesh
import os
import math

bl_info = {
    "name": "FastFX",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "File > Import-Export > 3DG1",
    "description": "Import/Export Fundoshi-kun (3DG1) format shapes, with additional tools.",
    "category": "Import-Export",
}


# =========================
# Import Operator
# =========================
class Import3DG1(bpy.types.Operator):
    """Import a 3DG1 File"""
    bl_idname = "import_mesh.3dg1"
    bl_label = "Import 3DG1 (.3dg1)"
    bl_options = {'PRESET', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        return read_3dg1(self.filepath, context)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# =========================
# Export Operator
# =========================
class Export3DG1(bpy.types.Operator):
    """Export to 3DG1 format"""
    bl_idname = "export_mesh.3dg1"
    bl_label = "Export 3DG1"
    bl_options = {'PRESET'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Selected object is not a mesh")
            return {'CANCELLED'}
        
        write_3dg1(self.filepath, obj)
        self.report({'INFO'}, f"Exported to {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


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

# =========================
# Hex color to RGB color Converter
# =========================
def hex_to_rgb(hex_color):
    """Converts a hex color code to RGB values."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4))


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
            if header != "3DG1":
                raise ValueError("Invalid file format: Not a 3DG1 file")
                return {'CANCELLED'}
            if header == "3DAN":
                raise ValueError("Animated 3DG1 files (3DAN) are not supported.")
                return {'CANCELLED'}

            # Read vertex count
            vertex_count = int(file.readline().strip())
            vertices = []

            # Read vertices
            for _ in range(vertex_count):
                line = file.readline().strip()
                x, y, z = map(int, line.split())
                vertices.append((x, y, z))

            # Read polygons
            polygons = []
            material_mapping = {}
            for line in file:
                if not line:  # End of file reached
                    break
                if line.strip() == chr(0x1A):  # EOF marker
                    break
                parts = line.split()
                npoints = int(parts[0])
                indices = list(map(int, parts[1:npoints + 1]))
                color_index = int(parts[npoints + 1])
                polygons.append((indices, color_index))
                if color_index not in material_mapping:
                    material_mapping[color_index] = f"FX{color_index}"

            # Predefined colors for materials (hex values)
            # Based on id_0_c material palette
            # Hex values from Bisquick's SFView
            # Descriptions from CoolK's COLOURS.TXT
            id_0_c_rgb = {
                0: "#668774",  # FX0 - Solid Dark Grey
                1: "#36533D",  # FX1 - Solid Darker Grey
                2: "#A54124",  # FX2 - Shaded Bright Red/Dark Red
                3: "#241687",  # FX3 - Shaded Blue/Bright Blue
                4: "#B88B36",  # FX4 - Shaded Bright Orange/Black
                5: "#4941AC",  # FX5 - Shaded Turquoise/Black
                6: "#47311C",  # FX6 - Solid Dark Red
                7: "#1C223D",  # FX7 - Solid Blue
                8: "#541E8B",  # FX8 - Shaded Red/blue (Purple)
                9: "#125012",  # FX9 - Shaded Green/Dark Green
                10: "#182918",  # FX10 - Solid Black
                11: "#2F3E2F",  # FX11 - Shaded Black/Dark Grey
                12: "#465346",  # FX12 - Solid Dark Grey
                13: "#5D695D",  # FX13 - Shaded Dark Grey/Darker Grey
                14: "#747E74",  # FX14 - Solid Darker Grey
                15: "#8B948B",  # FX15 - Shaded Darker Grey/Brighter Grey
                16: "#A2A9A2",  # FX16 - Solid Brighter Grey
                17: "#B9BEB9",  # FX17 - Shaded Brighter Grey/Bright Grey
                18: "#D0D4D0",  # FX18 - Solid Bright Grey
                19: "#E7E9E7",  # FX19 - Shaded Bright Grey/White
                20: "#FFFFFF",  # FX20 - Solid White
                21: "#8B1008",  # FX21 - Solid Dark Red (identical to 6)
                22: "#B02D18",  # FX22 - Shaded Bright Red/Dark Red (identical to 2)
                23: "#D54A29",  # FX23 - Solid Bright Red
                24: "#E17B35",  # FX24 - Shaded Bright Red/Orange
                25: "#EEAC41",  # FX25 - Solid Orange
                26: "#F6C555",  # FX26 - Shaded Bright Orange/Orange
                27: "#FFDE6A",  # FX27 - Solid Bright Orange
                28: "#2910AC",  # FX28 - Solid Blue
                29: "#412DC5",  # FX29 - Shaded Blue/Dark Turquoise
                30: "#5A4ADE",  # FX30 - Solid Dark Turquoise
                31: "#6A77EE",  # FX31 - Shaded Bright Blue/Dark Turquoise
                32: "#7BA4FF",  # FX32 - Solid Bright Blue
                33: "#97C9FF",  # FX33 - Shaded Turquoise/Dark Turquoise
                34: "#B4EEFF",  # FX34 - Solid Turquoise
                35: "#835A83",  # FX35 - Shaded Dark Red/Bright Blue
                36: "#A87794",  # FX36 - Shaded Bright Red/Bright Blue
                37: "#B4A8A0",  # FX37 - Shaded Bright Orange/Bright Blue
                38: "#BDC1B4",  # FX38 - Shaded Orange/Bright Blue
                39: "#209325",  # FX39 - Shaded Dark Green/Dark Grey
                40: "#00C500",  # FX40 - Solid Dark Green
                41: "#6AD56A",  # FX41 - Shaded Dark Green/Bright Turquoise
                42: "#182918",  # FX42 - Flashing (White/Turquoise/Bright Red/Green)
                43: "#D54A29",  # FX43 - Jet Fire (Bright Orange/Orange/Bright Red/Red)
                44: "#2910AC",  # FX44 - Blaster  (Bright Turquoise/Turquoise/Bright Blue/Blue)
                45: "#739483",  # FX45 - Flashing (White/Light Grey/Grey/Dark Grey)
                46: "#739483",  # FX46 - Flashing (Orange/Yellow/Turquoise/White)
                47: "#000000",  # FX47 - Invisible
                48: "#FFFFFF",  # FX48 - Asteroid texture
                49: "#FFFFFF",  # FX49 - "Wire" texture
                50: "#FFFFFF",  # FX50 ^
                51: "#FFFFFF",  # FX51 ^
                52: "#F6FFFF",  # FX52 - Fading   (Solid Red/Orange/Turquoise/Blue)
            }

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
                    # Convert hex to RGB and set the material's base color
                    hex_color = id_0_c_rgb.get(color_index, "#FFFFFF")  # Default to white if not defined
                    bsdf.inputs["Base Color"].default_value = hex_to_rgb(hex_color) + (1,)  # Add alpha value
                material_list.append(material)
                obj.data.materials.append(material)

            # Assign materials to faces
            for poly, (_, color_index) in zip(mesh.polygons, polygons):
                material_index = sorted(material_mapping.keys()).index(color_index)
                poly.material_index = material_index

            # Rotate the object by 90 degrees around the X-axis (compensate for 3DG1 coordinate inversion)
            obj.rotation_euler[0] = math.radians(90)  # X-axis rotation

        return {'FINISHED'}

    except Exception as e:
        bpy.ops.error(
            f"Error while importing file: {e}"
        )
        return {'CANCELLED'}

# =========================
# 3DG1 Exporter
# =========================
def write_3dg1(filepath, obj):
    # Open the file for writing
    with open(filepath, "w") as file:
        # Collect unique vertices and map them to indices
        unique_vertices = {}
        vertex_indices = []
        color_indices = []
        polygons = []
        vertex_count = 0

        # Write 3DG1 header
        file.write("3DG1\n")

        # Process the mesh data
        mesh = obj.data
        mesh.calc_loop_triangles()
        
        for poly in mesh.polygons:
            material_index = poly.material_index
            material = obj.material_slots[material_index].material
            
            if material and material.name.startswith("FX"):
                try:
                    color_index = int(material.name[2:])  # Extract color index from material name
                except ValueError:
                    color_index = 0  # Default color index if parsing fails
            else:
                color_index = 0  # Default color index if material doesn't match

            poly_vertices = []
            for loop_index in poly.loop_indices:
                vertex = mesh.vertices[mesh.loops[loop_index].vertex_index]
                co = tuple([round(v) for v in vertex.co])
                
                # Map unique vertices
                if co not in unique_vertices:
                    unique_vertices[co] = vertex_count
                    vertex_count += 1
                
                poly_vertices.append(unique_vertices[co])
            
            polygons.append((poly_vertices, color_index))
        
        # Write vertex count
        file.write(f"{len(unique_vertices)}\n")
        
        # Write vertices
        for vertex in unique_vertices:
            file.write(f"{vertex[0]} {vertex[1]} {vertex[2]}\n")
        
        # Write polygons
        for poly_vertices, color_index in polygons:
            file.write(f"{len(poly_vertices)} ")
            file.write(" ".join(map(str, poly_vertices)) + " ")
            file.write(f"{color_index}\n")
        
        # End-of-file marker
        file.write(chr(0x1A))


# =========================
# Vertex Operations Menu
# =========================
class VertexMenu(bpy.types.Menu):
    """Menu for vertex operations"""
    bl_label = "[FastFX] Vertex Operations"
    bl_idname = "OBJECT_MT_vertex_operations"

    def draw(self, context):
        layout = self.layout
        layout.operator(VertexOperation.bl_idname, text="Round Vertex Coordinates").operation = 'ROUND'
        layout.operator(VertexOperation.bl_idname, text="Truncate Vertex Coordinates").operation = 'TRUNCATE'


# =========================
# Menu Functions
# =========================
def menu_func_import(self, context):
    self.layout.operator(Import3DG1.bl_idname, text="Import 3DG1 (.3dg1)")


def menu_func_export(self, context):
    self.layout.operator(Export3DG1.bl_idname, text="Export 3DG1 (.3dg1)")


def menu_func_vertex_operations(self, context):
    self.layout.menu(VertexMenu.bl_idname, text="[FastFX] Vertex Operations")


# =========================
# Registration
# =========================
def register():
    bpy.utils.register_class(Import3DG1)
    bpy.utils.register_class(Export3DG1)
    bpy.utils.register_class(VertexOperation)
    bpy.utils.register_class(VertexMenu)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.VIEW3D_MT_object.append(menu_func_vertex_operations)


def unregister():
    bpy.utils.unregister_class(Import3DG1)
    bpy.utils.unregister_class(Export3DG1)
    bpy.utils.unregister_class(VertexOperation)
    bpy.utils.unregister_class(VertexMenu)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.VIEW3D_MT_object.remove(menu_func_vertex_operations)


if __name__ == "__main__":
    register()
