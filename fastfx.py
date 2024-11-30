import bpy
import bmesh
import os
import math

bl_info = {
    "name": "FastFX",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "File > Import-Export > 3DG1",
    "description": "Import/Export Fundoshi-kun (3DG1) shapes, with additional tools.",
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
# Vertex Operations
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
# Import Logic
# =========================
def read_3dg1(filepath, context):
    try:
        with open(filepath, 'r') as file:
            # Read and validate header
            header = file.readline().strip()
            if header != "3DG1":
                raise ValueError("Invalid file format: Not a 3DG1 file")

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
			# From CoolK's COLOURS.TXT
            id_0_c_rgb = {
                0: "#E7E7E7",  # FX0
                1: "#AAAAAA",  # FX1
                2: "#BA392A",  # FX2
                3: "#5144D4",  # FX3
                4: "#D8A950",  # FX4
                5: "#190646",  # FX5
                6: "#801009",  # FX6
                7: "#2411A3",  # FX7
                8: "#7C11A3",  # FX8
                9: "#2F9E28",  # FX9
                10: "#192419",  # FX10
                11: "#223022",  # FX11
                12: "#334933",  # FX12
                13: "#415D41",  # FX13
                14: "#4F724F",  # FX14
                15: "#99B2A4",  # FX15
                16: "#A4B4A4",  # FX16
                17: "#B1C1B1",  # FX17
                18: "#D0E2D2",  # FX18
                19: "#DDEAE1",  # FX19
                20: "#FFFFFF",  # FX20
                21: "#801009",  # FX21
                22: "#D54437",  # FX22
                23: "#D14025",  # FX23
                24: "#C75821",  # FX24
                25: "#EDA33A",  # FX25
                26: "#FFA624",  # FX26
                27: "#FFD961",  # FX27
                28: "#2411A3",  # FX28
                29: "#2813B5",  # FX29
                30: "#5041DA",  # FX30
                31: "#7D82FF",  # FX31
                32: "#709AFF",  # FX32
                33: "#2BBCAE",  # FX33
                34: "#3ED9C9",  # FX34
                35: "#61216C",  # FX35
                36: "#782985",  # FX36
                37: "#8D5694",  # FX37
                38: "#B094A4",  # FX38
                39: "#2D4F3D",  # FX39
                40: "#1A2E23",  # FX40
                41: "#24405A",  # FX41
                42: "#A6C0FF",  # FX42
                43: "#D14025",  # FX43
                44: "#AEEBFF",  # FX44
                45: "#D0E2D4",  # FX45
                46: "#D0E2FF",  # FX46
                47: "#010101",  # FX47
                48: "#5E5010",  # FX48
                49: "#FF2D25",  # FX49
                50: "#FFFFFF",  # FX50
                51: "#FFFFFF",  # FX51
                52: "#952D25",  # FX52
            }

            # Create a new mesh in Blender
            mesh = bpy.data.meshes.new("Imported3DG1")
            mesh.from_pydata(vertices, [], [poly[0] for poly in polygons])
            obj = bpy.data.objects.new("Imported3DG1", mesh)
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
                    r, g, b = [int(hex_color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
                    bsdf.inputs['Base Color'].default_value = (r, g, b, 1.0)  # RGBA with full opacity
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
# Export Logic
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
# Custom Menu
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
