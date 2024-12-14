import bpy, mathutils
import bmesh
import os
import math
from bpy_extras.io_utils import ImportHelper
import struct

bl_info = {
    "name": "FastFX",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "File > Import-Export > 3DG1",
    "description": "Import/Export Fundoshi-kun (3DG1) format shapes, with additional tools.",
    "category": "Import-Export",
}

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
# Colbox importer operator
# =========================
class OBJECT_OT_import_colboxes_clipboard(bpy.types.Operator):
    """Import Collision Boxes From Clipboard"""
    bl_idname = "object.import_colboxes_clipboard"
    bl_label = "Import Colboxes From Clipboard"

    def execute(self, context):
        import_colboxes_from_clipboard()
        self.report({'INFO'}, f"Collision box(es) imported successfully!")
        return {'FINISHED'}

# =========================
# Colbox exporter operator
# =========================
class OBJECT_OT_export_colboxes(bpy.types.Operator):
    """Export Collision Boxes to Clipboard"""
    bl_idname = "object.export_colboxes"
    bl_label = "Export Colboxes to Clipboard"

    def execute(self, context):
        export_colboxes(context)
        self.report({'INFO'}, f"Collision box(es) exported successfully!")
        return {'FINISHED'}

# =========================
# Colbox exporter
# =========================
def export_colboxes(context):
    colbox_data = []

    for obj in context.selected_objects:
        if obj.type != 'EMPTY':
            continue

        # Fetch custom collision box properties
        label = obj.get("colbox_label", obj.name)
        linked_label = obj.get("colbox_linked_label", "0")
        offset = obj.get("colbox_offset", [0, 0, 0])
        rotation = obj.get("colbox_rotation", "norot")
        dimensions = obj.get("colbox_dimensions", [1, 1, 1])
        flags_set = obj.get("colbox_flags_set", "0")
        flags_clear = obj.get("colbox_flags_clear", "0")
        scale = obj.get("colbox_scale", 1)

        # Create collision box string
        colbox_str = f"{label}\tcolbox\t{linked_label}," \
                     f"{offset[0]},{offset[1]},{offset[2]}," \
                     f"{rotation}," \
                     f"{dimensions[0]},{dimensions[1]},{dimensions[2]}," \
                     f"{flags_set},{flags_clear},{scale}"
        colbox_data.append(colbox_str)

    # Copy all collision boxes to the clipboard
    bpy.context.window_manager.clipboard = "\n".join(colbox_data)
    return {'FINISHED'}

# =========================
# Colbox importer
# =========================
def import_colboxes_from_clipboard():
    clipboard_content = bpy.context.window_manager.clipboard
    lines = clipboard_content.splitlines()

    for line in lines:
        if not line.strip():
            continue  # Skip empty lines

        # Parse the colbox definition
        parts = line.split("\t")
        if len(parts) != 3 or parts[1] != "colbox":
            print(f"Invalid colbox line: {line}")
            continue

        label = parts[0]
        colbox_data = parts[2].split(",")

        # Extract individual fields
        linked_label = colbox_data[0]
        offset = list(map(int, colbox_data[1:4]))
        rotation = colbox_data[4]
        dimensions = list(map(int, colbox_data[5:8]))
        flags_set = colbox_data[8]
        flags_clear = colbox_data[9]
        scale = int(colbox_data[10]) if len(colbox_data) > 10 else 0  # Default to 0 if scale is missing

        # Invert Y (Blender Z)
        offset[1] = offset[1] * -1

        # Swap Y and Z axes for Blender
        offset[1], offset[2] = offset[2], offset[1]
        dimensions[1], dimensions[2] = dimensions[2], dimensions[1]

        # Find or create an object for the colbox
        obj = bpy.data.objects.get(label) or bpy.data.objects.new(label, None)
        bpy.context.collection.objects.link(obj)

        # Set the object type to EMPTY and its display type to CUBE
        obj.empty_display_type = 'CUBE'

        # Size the empty to match the dimensions
        obj.empty_display_size = max(dimensions)  # Use the largest dimension for uniform scaling
        obj.scale = (dimensions[0] / obj.empty_display_size, 
                     dimensions[1] / obj.empty_display_size, 
                     dimensions[2] / obj.empty_display_size)

        # Adjust location based on offset and scale
        scaled_offset = [o * (2 ** scale) for o in offset]
        obj.location = scaled_offset

        # Invert Z again so the properties are correct for manual exporting
        offset[2] = offset[2] * -1

        # Swap Y and Z axes back for same reason
        offset[1], offset[2] = offset[2], offset[1]
        dimensions[1], dimensions[2] = dimensions[2], dimensions[1]

        # Store colbox data in the object
        obj["colbox_label"] = label
        obj["colbox_linked_label"] = linked_label
        obj["colbox_offset"] = offset
        obj["colbox_rotation"] = rotation
        obj["colbox_dimensions"] = dimensions
        obj["colbox_flags_set"] = flags_set
        obj["colbox_flags_clear"] = flags_clear
        obj["colbox_scale"] = scale

    return {'FINISHED'}

# =========================
# Update colbox visual from its properties
# =========================
class OBJECT_OT_update_colboxes(bpy.types.Operator):
    """Update collision box visuals based on its properties"""
    bl_idname = "object.update_colboxes"
    bl_label = "Update Colboxes From Properties"

    def execute(self, context):
        updated_count = 0
        for obj in context.selected_objects:
            if "colbox_label" in obj:
                update_colbox(obj)
                updated_count += 1

        self.report({'INFO'}, f"Updated {updated_count} collision boxes")
        return {'FINISHED'}

def update_colbox(obj):
    """
    Updates the visual and transformation properties of a collision box based on its stored properties.
    """
    if not obj or "colbox_label" not in obj:
        print(f"Object '{obj.name}' is not a valid collision box.")
        return

    # Fetch stored properties
    label = obj.get("colbox_label", obj.name)
    linked_label = obj.get("colbox_linked_label", "0")
    offset = obj.get("colbox_offset", [0, 0, 0])
    rotation = obj.get("colbox_rotation", "norot")
    dimensions = obj.get("colbox_dimensions", [1, 1, 1])
    scale = obj.get("colbox_scale", 0)

    # Adjust offset: invert Y and swap Y/Z for Blender
    offset[1] = offset[1] * -1
    offset[1], offset[2] = offset[2], offset[1]

    # Adjust dimensions: swap Y/Z for Blender
    dimensions[1], dimensions[2] = dimensions[2], dimensions[1]

    # Update the EMPTY's visual size and location
    obj.empty_display_type = 'CUBE'
    obj.empty_display_size = max(dimensions)  # Use the largest dimension for consistent scaling
    obj.scale = (dimensions[0] / obj.empty_display_size,
                 dimensions[1] / obj.empty_display_size,
                 dimensions[2] / obj.empty_display_size)

    # Apply offset to location
    obj.location = offset

    # Adjust offset: invert Y and swap Y/Z for Blender
    offset[2] = offset[2] * -1
    offset[1], offset[2] = offset[2], offset[1]

    # Adjust dimensions: swap Y/Z for Blender
    dimensions[1], dimensions[2] = dimensions[2], dimensions[1]

    # Store colbox data in the object
    obj["colbox_dimensions"] = dimensions
    obj["colbox_scale"] = scale

    print(f"Collision box '{label}' updated successfully!")

# =========================
# Update colbox position based on its visual position
# =========================
class OBJECT_OT_update_colbox_offsets(bpy.types.Operator):
    """Update colbox offsets based on the current position of selected objects"""
    bl_idname = "object.update_colbox_offsets"
    bl_label = "Update Colbox Positions"

    def execute(self, context):
        updated_count = 0
        for obj in context.selected_objects:
            if "colbox_label" in obj:
                update_colbox_offset(obj)
                updated_count += 1

        self.report({'INFO'}, f"Updated offsets for {updated_count} collision boxes")
        return {'FINISHED'}


def update_colbox_offset(obj):
    """
    Updates the colbox_offset property based on the current position of the object in the scene.
    """
    if not obj or "colbox_label" not in obj:
        print(f"Object '{obj.name}' is not a valid collision box.")
        return

    # Get the current location of the object
    location = list(obj.location)

    # Adjust for Blender's coordinate system: swap Y/Z, invert Y
    location[2] = location[2] * -1  # Invert Z (Blender's Z = target's Y)
    location[1], location[2] = location[2], location[1]  # Swap Y and Z

    # Colbox coordinates must be whole numbers
    location[0] = math.trunc(location[0])
    location[1] = math.trunc(location[1])
    location[2] = math.trunc(location[2])

    # Update the colbox_offset property
    obj["colbox_offset"] = location

    print(f"Collision box '{obj.name}' offset updated to {location}!")

# =========================
# Generate a colbox for a selected mesh
# =========================
class OBJECT_OT_generate_colbox(bpy.types.Operator):
    """Generate a collision box that fits the selected mesh"""
    bl_idname = "object.generate_colbox"
    bl_label = "Generate Colbox for Mesh"

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "No mesh object selected")
            return {'CANCELLED'}

        generate_colbox_from_mesh(obj)
        self.report({'INFO'}, f"Collision box created for '{obj.name}'")
        return {'FINISHED'}


def generate_colbox_from_mesh(obj):
    """
    Generate a collision box that is scaled to fit the given mesh object.
    The colbox position and dimensions are rounded to whole integers.
    """
    if not obj or obj.type != 'MESH':
        print("Selected object is not a mesh.")
        return

    # Calculate the bounding box dimensions and position
    min_corner = [int(round(coord)) for coord in obj.bound_box[0]]
    max_corner = [int(round(coord)) for coord in obj.bound_box[6]]
    
    dimensions = [
        max_corner[0] - min_corner[0],
        max_corner[1] - min_corner[1],
        max_corner[2] - min_corner[2],
    ]
    
    center_position = [
        int(round((min_corner[0] + max_corner[0]) / 2)),
        int(round((min_corner[1] + max_corner[1]) / 2)),
        int(round((min_corner[2] + max_corner[2]) / 2)),
    ]

    # Halve dimensions to fit around object
    dimensions[0] = math.trunc(dimensions[0]/2)
    dimensions[1] = math.trunc(dimensions[1]/2)
    dimensions[2] = math.trunc(dimensions[2]/2)

    # Swap Y and Z for Blender's coordinate system
    center_position[1], center_position[2] = center_position[2], center_position[1]
    dimensions[1], dimensions[2] = dimensions[2], dimensions[1]

    # Create the colbox
    colbox_label = f"{obj.name}_col"
    colbox = bpy.data.objects.new(colbox_label, None)
    bpy.context.collection.objects.link(colbox)

    # Set the colbox as an empty object with a cube display
    colbox.empty_display_type = 'CUBE'

    # Set the dimensions and location
    colbox.empty_display_size = max(dimensions)
    colbox.scale = (
        dimensions[0] / colbox.empty_display_size,
        dimensions[1] / colbox.empty_display_size,
        dimensions[2] / colbox.empty_display_size,
    )
    colbox.location = center_position

    # Swap Y and Z for target coordinate system
    center_position[1], center_position[2] = center_position[2], center_position[1]
    dimensions[1], dimensions[2] = dimensions[2], dimensions[1]

    # Assign colbox properties
    colbox["colbox_label"] = colbox_label
    colbox["colbox_linked_label"] = "0"
    colbox["colbox_offset"] = center_position
    colbox["colbox_rotation"] = "norot"
    colbox["colbox_dimensions"] = dimensions
    colbox["colbox_flags_set"] = "HF1"
    colbox["colbox_flags_clear"] = "0"
    colbox["colbox_scale"] = 0  # Default scale

    update_colbox_offset(colbox)

    print(f"Collision box '{colbox_label}' created for mesh '{obj.name}'.")
    return colbox


# =========================
# Hex color to RGB color Converter
# =========================
def srgb_to_linearrgb(c):
    if c < 0:
        return 0
    elif c < 0.04045:
        return c / 12.92
    else:
        return ((c + 0.055) / 1.055) ** 2.4

def hex_to_rgb(hex_color, alpha=1.0):
    """Converts a hex color code to Blender-compatible linear RGB values."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (srgb_to_linearrgb(r), srgb_to_linearrgb(g), srgb_to_linearrgb(b), alpha)

# =========================
# Simple Color Palette Dictionary
# =========================
# Predefined colors for materials when a shape is imported (hex values)
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

# =========================
# Super FX Material Color Palette Dictionary
# =========================
# Super FX Material color palette
id_0_c_components_rgb = {
    0: { # COLLITE COLORS BEGIN
        "Colour 1": "#C6CFD6",
        "Colour 2": "#A59E9C",
        "Colour 3": "#847173",
        "Colour 4": "#6B3839",
    },
    1: {
        "Colour 1": "#A59E9C",
        "Colour 2": "#847173",
        "Colour 3": "#6B3839",
        "Colour 4": "#391010",
    },
    2: {
        "Colour 1": "#FFDF5A",
        "Colour 2": "#FFB631",
        "Colour 3": "#F76121",
        "Colour 4": "#AD2800",
    },
    3: {
        "Colour 1": "#F7FFFF",
        "Colour 2": "#BDEFFF",
        "Colour 3": "#2928BD",
        "Colour 4": "#38121F",
    },
    4: {
        "Colour 1": "#D5D1AF",
        "Colour 2": "#F9DA58",
        "Colour 3": "#F76121",
        "Colour 4": "#391010",
    },
    5: {
        "Colour 1": "#C6CFD6",
        "Colour 2": "#BDEFFF",
        "Colour 3": "#6351DE",
        "Colour 4": "#391010",
    },
    6: {
        "Colour 1": "#FFDF5A",
        "Colour 2": "#FFB631",
        "Colour 3": "#F76121",
        "Colour 4": "#391010",
    },
    7: {
        "Colour 1": "#BDEFFF",
        "Colour 2": "#8CBEEF",
        "Colour 3": "#6351DE",
        "Colour 4": "#2928BD",
    },
    8: {
        "Colour 1": "#F76121",
        "Colour 2": "#BDEFFF",
        "Colour 3": "#6351DE",
        "Colour 4": "#2928BD",
        "Carry Over": "1.0",
    },
    9: {
        "Colour 1": "#008E00",
        "Colour 2": "#847173",
        "Colour 3": "#6B3839",
        "Colour 4": "#391010",
        "Carry Over": "1.0",
    },
    10: { #Mostly COLNORM colors begin
        "Colour 1": "#391010",
        "Colour 2": "#391010",
        "Colour 3": "#391010",
        "Colour 4": "#391010",
        "Carry Over": "1.0",
    },
    11: { # shaded/dithered solid colors go tile color 1(2x), tile color 2 (2x)
        "Colour 1": "#391010",
        "Colour 2": "#391010",
        "Colour 3": "#6B3839",
        "Colour 4": "#6B3839",
        "Carry Over": "1.0",
    },
    12: {
        "Colour 1": "#6B3839",
        "Colour 2": "#6B3839",
        "Colour 3": "#6B3839",
        "Colour 4": "#6B3839",
        "Carry Over": "1.0",
    },
    13: {
        "Colour 1": "#847173",
        "Colour 2": "#847173",
        "Colour 3": "#6B3839",
        "Colour 4": "#6B3839",
        "Carry Over": "1.0",
    },
    14: {
        "Colour 1": "#847173",
        "Colour 2": "#847173",
        "Colour 3": "#847173",
        "Colour 4": "#847173",
        "Carry Over": "1.0",
    },
    15: {
        "Colour 1": "#A59E9C",
        "Colour 2": "#A59E9C",
        "Colour 3": "#847173",
        "Colour 4": "#847173",
        "Carry Over": "1.0",
    },
    16: {
        "Colour 1": "#A59E9C",
        "Colour 2": "#A59E9C",
        "Colour 3": "#A59E9C",
        "Colour 4": "#A59E9C",
        "Carry Over": "1.0",
    },
    17: {
        "Colour 1": "#C6CFD6",
        "Colour 2": "#C6CFD6",
        "Colour 3": "#A59E9C",
        "Colour 4": "#A59E9C",
        "Carry Over": "1.0",
    },
    18: {
        "Colour 1": "#C6CFD6",
        "Colour 2": "#C6CFD6",
        "Colour 3": "#C6CFD6",
        "Colour 4": "#C6CFD6",
        "Carry Over": "1.0",
    },
    19: {
        "Colour 1": "#F7FFFF",
        "Colour 2": "#F7FFFF",
        "Colour 3": "#C6CFD6",
        "Colour 4": "#C6CFD6",
        "Carry Over": "1.0",
    },
    20: {
        "Colour 1": "#F7FFFF",
        "Colour 2": "#F7FFFF",
        "Colour 3": "#F7FFFF",
        "Colour 4": "#F7FFFF",
        "Carry Over": "1.0",
    },
    21: {
        "Colour 1": "#AD2800",
        "Colour 2": "#AD2800",
        "Colour 3": "#AD2800",
        "Colour 4": "#AD2800",
        "Carry Over": "1.0",
    },
    22: {
        "Colour 1": "#F76121",
        "Colour 2": "#F76121",
        "Colour 3": "#AD2800",
        "Colour 4": "#AD2800",
        "Carry Over": "1.0",
    },
    23: {
        "Colour 1": "#F76121",
        "Colour 2": "#F76121",
        "Colour 3": "#F76121",
        "Colour 4": "#F76121",
        "Carry Over": "1.0",
    },
    24: {
        "Colour 1": "#F76121",
        "Colour 2": "#F76121",
        "Colour 3": "#FFB631",
        "Colour 4": "#FFB631",
        "Carry Over": "1.0",
    },
    25: {
        "Colour 1": "#FFB631",
        "Colour 2": "#FFB631",
        "Colour 3": "#FFB631",
        "Colour 4": "#FFB631",
        "Carry Over": "1.0",
    },
    26: {
        "Colour 1": "#FFDF5A",
        "Colour 2": "#FFDF5A",
        "Colour 3": "#FFB631",
        "Colour 4": "#FFB631",
        "Carry Over": "1.0",
    },
    27: {
        "Colour 1": "#FFDF5A",
        "Colour 2": "#FFDF5A",
        "Colour 3": "#FFDF5A",
        "Colour 4": "#FFDF5A",
        "Carry Over": "1.0",
    },
    28: {
        "Colour 1": "#2928BD",
        "Colour 2": "#2928BD",
        "Colour 3": "#2928BD",
        "Colour 4": "#2928BD",
        "Carry Over": "1.0",
    },
    29: {
        "Colour 1": "#6351DE",
        "Colour 2": "#6351DE",
        "Colour 3": "#2928BD",
        "Colour 4": "#2928BD",
        "Carry Over": "1.0",
    },
    30: {
        "Colour 1": "#6351DE",
        "Colour 2": "#6351DE",
        "Colour 3": "#6351DE",
        "Colour 4": "#6351DE",
        "Carry Over": "1.0",
    },
    31: {
        "Colour 1": "#8CBEEF",
        "Colour 2": "#8CBEEF",
        "Colour 3": "#6351DE",
        "Colour 4": "#6351DE",
        "Carry Over": "1.0",
    },
    32: {
        "Colour 1": "#8CBEEF",
        "Colour 2": "#8CBEEF",
        "Colour 3": "#8CBEEF",
        "Colour 4": "#8CBEEF",
        "Carry Over": "1.0",
    },
    33: {
        "Colour 1": "#8CBEEF",
        "Colour 2": "#8CBEEF",
        "Colour 3": "#BDEFFF",
        "Colour 4": "#BDEFFF",
        "Carry Over": "1.0",
    },
    34: {
        "Colour 1": "#BDEFFF",
        "Colour 2": "#BDEFFF",
        "Colour 3": "#BDEFFF",
        "Colour 4": "#BDEFFF",
        "Carry Over": "1.0",
    },
    35: {
        "Colour 1": "#AD2800",
        "Colour 2": "#AD2800",
        "Colour 3": "#6351DE",
        "Colour 4": "#6351DE",
        "Carry Over": "1.0",
    },
    36: {
        "Colour 1": "#F76121",
        "Colour 2": "#F76121",
        "Colour 3": "#6351DE",
        "Colour 4": "#6351DE",
        "Carry Over": "1.0",
    },
    37: {
        "Colour 1": "#6351DE",
        "Colour 2": "#6351DE",
        "Colour 3": "#FFB631",
        "Colour 4": "#FFB631",
        "Carry Over": "1.0",
    },
    38: {
        "Colour 1": "#FFDF5A",
        "Colour 2": "#FFDF5A",
        "Colour 3": "#6351DE",
        "Colour 4": "#6351DE",
        "Carry Over": "1.0",
    },
    39: {
        "Colour 1": "#00C700",
        "Colour 2": "#00C700",
        "Colour 3": "#6B3839",
        "Colour 4": "#6B3839",
        "Carry Over": "1.0",
    },
    40: {
        "Colour 1": "#00C700",
        "Colour 2": "#00C700",
        "Colour 3": "#00C700",
        "Colour 4": "#00C700",
        "Carry Over": "1.0",
    },
    41: {
        "Colour 1": "#00C700",
        "Colour 2": "#00C700",
        "Colour 3": "#C6CFD6",
        "Colour 4": "#C6CFD6",
        "Carry Over": "1.0",
    },
    42: {
        "Colour 1": "#00C700",
        "Colour 2": "#00C700",
        "Colour 3": "#00C700",
        "Colour 4": "#00C700",
        "Carry Over": "1.0",
    },
    43: { #flashes
        "Colour 1": "#AD2800",
        "Colour 2": "#AD2800",
        "Colour 3": "#AD2800",
        "Colour 4": "#AD2800",
        "Carry Over": "1.0",
    },
    44: { #flashes
        "Colour 1": "#2928BD",
        "Colour 2": "#2928BD",
        "Colour 3": "#2928BD",
        "Colour 4": "#2928BD",
        "Carry Over": "1.0",
    },
    45: { #flashes
        "Colour 1": "#847173",
        "Colour 2": "#847173",
        "Colour 3": "#847173",
        "Colour 4": "#847173",
        "Carry Over": "1.0",
    },
    46: {
        "Colour 1": "#AD2800",
        "Colour 2": "#AD2800",
        "Colour 3": "#FFB631",
        "Colour 4": "#FFB631",
        "Carry Over": "1.0",
    },
    47: {
        "Colour 1": "#000000",
        "Colour 2": "#000000",
        "Colour 3": "#000000",
        "Colour 4": "#000000",
        "Carry Over": "1.0",
    },
    48: { # texture
        "Colour 1": "#FFFFFF",
        "Colour 2": "#FFFFFF",
        "Colour 3": "#FFFFFF",
        "Colour 4": "#FFFFFF",
    },
    49: { # texture
        "Colour 1": "#FFFFFF",
        "Colour 2": "#FFFFFF",
        "Colour 3": "#FFFFFF",
        "Colour 4": "#FFFFFF",
    },
    50: { # texture
        "Colour 1": "#FFFFFF",
        "Colour 2": "#FFFFFF",
        "Colour 3": "#FFFFFF",
        "Colour 4": "#FFFFFF",
    },
    51: { # texture
        "Colour 1": "#FFFFFF",
        "Colour 2": "#FFFFFF",
        "Colour 3": "#FFFFFF",
        "Colour 4": "#FFFFFF",
    },
    52: {
        "Colour 1": "#AD2800",
        "Colour 2": "#AD2800",
        "Colour 3": "#AD2800",
        "Colour 4": "#AD2800",
        "Carry Over": "1.0",
    },
}


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
                vertices.append((x, y, z))

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
def write_3dg1(filepath, obj, sort_mode="distance"):
    """
    Exports a mesh object to 3DG1 format with customizable sorting modes.
    
    :param filepath: Path to write the 3DG1 file.
    :param obj: Blender mesh object to export.
    :param sort_mode: Sorting mode ("distance", "material", "none").
    """

    # Gets distance from origin
    def distance_from_origin(point):
        return math.sqrt(point[0]**2 + point[1]**2 + point[2]**2)

    # Open the file for writing
    with open(filepath, "w") as file:
        # Collect unique vertices and map them to indices
        unique_vertices = {}
        vertex_count = 0
        polygons = []
        edges = []  # Store edges for colored lines

        # Write 3DG1 header
        file.write("3DG1\n")

        # Process the mesh data
        mesh = obj.data
        mesh.calc_loop_triangles()

        for poly in mesh.polygons:
            material_index = poly.material_index
            material = obj.material_slots[material_index].material

            if material:
                # Check if the material represents an edge (FE#)
                if material.name.startswith("FE"):
                    try:
                        edge_color_index = int(material.name[2:])  # Extract color index for edges
                    except ValueError:
                        edge_color_index = 0  # Default to 0 if parsing fails

                    # Convert the face to edges
                    for i in range(len(poly.vertices)):
                        v1 = poly.vertices[i]
                        v2 = poly.vertices[(i + 1) % len(poly.vertices)]  # Wrap around to create a closed edge
                        co1 = tuple([round(v) for v in mesh.vertices[v1].co])
                        co2 = tuple([round(v) for v in mesh.vertices[v2].co])

                        # Map unique vertices
                        if co1 not in unique_vertices:
                            unique_vertices[co1] = vertex_count
                            vertex_count += 1
                        if co2 not in unique_vertices:
                            unique_vertices[co2] = vertex_count
                            vertex_count += 1

                        # Calculate the midpoint for sorting
                        midpoint = tuple((c1 + c2) / 2 for c1, c2 in zip(co1, co2))
                        edges.append((unique_vertices[co1], unique_vertices[co2], edge_color_index, midpoint))

                # Otherwise, handle it as a polygon
                elif material.name.startswith("FX"):
                    try:
                        color_index = int(material.name[2:])  # Extract color index for polygons
                    except ValueError:
                        color_index = 0  # Default to 0 if parsing fails

                    poly_vertices = []
                    for loop_index in poly.loop_indices:
                        vertex = mesh.vertices[mesh.loops[loop_index].vertex_index]
                        co = tuple([round(v) for v in vertex.co])

                        # Map unique vertices
                        if co not in unique_vertices:
                            unique_vertices[co] = vertex_count
                            vertex_count += 1

                        poly_vertices.append(unique_vertices[co])

                    # Calculate the centroid for sorting
                    centroid = tuple(
                        sum(mesh.vertices[v].co[i] for v in poly.vertices) / len(poly.vertices)
                        for i in range(3)
                    )
                    polygons.append((poly_vertices, color_index, centroid, material_index))

        # Apply sorting based on the selected mode
        if sort_mode == "distance":
            polygons.sort(key=lambda p: distance_from_origin(p[2]))  # Sort polygons by centroid distance from origin
            edges.sort(key=lambda e: distance_from_origin(e[3]))  # Sort edges by midpoint distance from origin
        elif sort_mode == "material":
            polygons.sort(key=lambda p: p[3])  # Sort by material index
        # If sort_mode is "none", no sorting is applied

        if sort_mode == "distance":
            # Reverse the order so farthest elements are written last
            polygons.reverse()
            edges.reverse()

        # Write vertex count
        file.write(f"{len(unique_vertices)}\n")

        # Write vertices
        for vertex in unique_vertices:
            file.write(f"{vertex[0]} {vertex[1]} {vertex[2]}\n")

        # Write polygons
        for poly_vertices, color_index, _, _ in polygons:
            file.write(f"{len(poly_vertices)} ")
            file.write(" ".join(map(str, poly_vertices)) + " ")
            file.write(f"{color_index}\n")

        # Write edges
        for v1, v2, color_index, _ in edges:
            file.write(f"2 {v1} {v2} {color_index}\n")

        # End-of-file marker
        file.write(chr(0x1A))

    return {'FINISHED'}

# =========================
# ASM BSP/GZS Importer Operator
# =========================
class ImportBSPOperator(bpy.types.Operator, ImportHelper):
    """Import Star Fox ASM BSP/GZS File"""
    bl_idname = "import_mesh.bsp"
    bl_label = "Import Star Fox ASM BSP/GZS File"
    bl_options = {'PRESET', 'UNDO'}

    # Filter to show only asm/bsp files in the file browser
    filter_glob: bpy.props.StringProperty(default="*.asm;*.bsp", options={'HIDDEN'})

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
        material_indices = []
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

                    y = -y  # Invert Y

                    points.append((x, y, z))
                    if invert_x:
                        points.append((-x, y, z))

                # Handle faces
                # Make sure the shape itself isn't named "Faces"
                if is_face_section and stripped_line.startswith("ShapeHdr"):
                    is_face_section = False

                if is_face_section and stripped_line.startswith("Face"):
                    parts = stripped_line.split("\t")
                    face_data = parts[1]
                    face_parts = face_data.split(",")

                    material_index = int(face_parts[0])  # Material index
                    num_points = int(stripped_line[4])  # "FaceX", X = number of points
                    point_indices = list(map(int, face_parts[-num_points:]))

                    # Invert the winding order of the face for normal inversion
                    point_indices.reverse()  # Reverse the order of indices

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

                    faces.append(tuple(point_indices))
                    material_indices.append(material_map[material_name])

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

            # Rotate the object by 90 degrees around the X-axis (compensate for 3DG1 coordinate inversion)
            obj.rotation_euler[0] = math.radians(90)  # X-axis rotation

            self.report({'INFO'}, f"Mesh '{mesh_name}' created with {len(points)} points and {len(faces)} faces.")
        except Exception as e:
            raise RuntimeError(f"Error processing BSP file: {e}")

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
                points[frame].append((x, y, z))
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

            # Rotate the object by 90 degrees around the X-axis (compensate for 3DG1 coordinate inversion)
            obj.rotation_euler[0] = math.radians(90)  # X-axis rotation

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
def write_3dan(filepath, meshes, frame_number):
    """
    Writes the 3DAN file format.

    :param filepath: The output file path.
    :param meshes: List of Blender mesh objects.
    :param frame_number: Total number of frames.
    """
    # Sort meshes by name to ensure frames are in the correct order
    sorted_meshes = sorted(meshes, key=lambda mesh: mesh.name)

    with open(filepath, "w") as f:
        # Header
        f.write("3DAN\n")
        f.write(f"{len(sorted_meshes[0].vertices)}\n")  # Total unique points (assume consistent vertex count)
        f.write(f"{frame_number}\n")  # Number of animation frames

        # Write point data per frame
        for frame_index in range(frame_number):
            mesh = sorted_meshes[frame_index]
            for vertex in mesh.vertices:
                # Convert vertex coordinates to integers
                x, y, z = (int(round(coord)) for coord in vertex.co)
                f.write(f"{x} {y} {z}\n")

        # Write polygon data (from the first frame's mesh)
        base_mesh = sorted_meshes[0]
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
# 3DAN Exporter Operator
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

        # Collect meshes for frames
        frame_meshes = []
        for obj in objects:
            if obj.type == "MESH":
                frame_meshes.append(obj.data)

        if len(frame_meshes) < 1:
            self.report({'ERROR'}, "No meshes found for export.")
            return {'CANCELLED'}

        # Assume the number of meshes corresponds to the number of frames
        frame_number = len(frame_meshes)

        # Export to 3DAN
        write_3dan(filepath, frame_meshes, frame_number)

        self.report({'INFO'}, f"Exported {frame_number} frames to {filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# =========================
# Super FX Material
# =========================
#initialize Super FX node group
def super_fx_node_group():

    mat = bpy.data.materials.new(name = "SuperFX")
    mat.use_nodes = True

    """Creates the Super FX node group and a material using it."""
    # Ensure the node group doesn't already exist
    if "Super FX" in bpy.data.node_groups:
        return

    super_fx = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = "Super FX")

    mat = bpy.data.materials.new(name = "SuperFX")
    mat.use_nodes = True

    #initialize super_fx nodes
    #node Group Output
    group_output = super_fx.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True
    #super_fx outputs
    #output Emission
    super_fx.outputs.new('NodeSocketShader', "Emission")
    super_fx.outputs[0].attribute_domain = 'POINT'



    #node Mix.006
    mix_006 = super_fx.nodes.new("ShaderNodeMix")
    mix_006.name = "Mix.006"
    mix_006.blend_type = 'MIX'
    mix_006.clamp_factor = True
    mix_006.clamp_result = False
    mix_006.data_type = 'RGBA'
    mix_006.factor_mode = 'UNIFORM'

    #node Reroute
    reroute = super_fx.nodes.new("NodeReroute")
    reroute.name = "Reroute"
    #node Math.007
    math_007 = super_fx.nodes.new("ShaderNodeMath")
    math_007.name = "Math.007"
    math_007.hide = True
    math_007.operation = 'ADD'
    math_007.use_clamp = False

    #node Map Range.001
    map_range_001 = super_fx.nodes.new("ShaderNodeMapRange")
    map_range_001.name = "Map Range.001"
    map_range_001.hide = True
    map_range_001.clamp = True
    map_range_001.data_type = 'FLOAT'
    map_range_001.interpolation_type = 'LINEAR'
    #From Min
    map_range_001.inputs[1].default_value = 0.5
    #From Max
    map_range_001.inputs[2].default_value = 0.5001000165939331
    #To Min
    map_range_001.inputs[3].default_value = 0.0
    #To Max
    map_range_001.inputs[4].default_value = 1.0

    #node Reroute.015
    reroute_015 = super_fx.nodes.new("NodeReroute")
    reroute_015.name = "Reroute.015"
    #node Map Range.004
    map_range_004 = super_fx.nodes.new("ShaderNodeMapRange")
    map_range_004.name = "Map Range.004"
    map_range_004.hide = True
    map_range_004.clamp = True
    map_range_004.data_type = 'FLOAT'
    map_range_004.interpolation_type = 'LINEAR'
    #From Min
    map_range_004.inputs[1].default_value = 0.5
    #From Max
    map_range_004.inputs[2].default_value = 0.5001000165939331
    #To Min
    map_range_004.inputs[3].default_value = 0.0
    #To Max
    map_range_004.inputs[4].default_value = 1.0

    #node Map Range.005
    map_range_005 = super_fx.nodes.new("ShaderNodeMapRange")
    map_range_005.name = "Map Range.005"
    map_range_005.hide = True
    map_range_005.clamp = True
    map_range_005.data_type = 'FLOAT'
    map_range_005.interpolation_type = 'LINEAR'
    #From Min
    map_range_005.inputs[1].default_value = 0.5
    #From Max
    map_range_005.inputs[2].default_value = 0.5001000165939331
    #To Min
    map_range_005.inputs[3].default_value = 0.0
    #To Max
    map_range_005.inputs[4].default_value = 1.0

    #node Math.016
    math_016 = super_fx.nodes.new("ShaderNodeMath")
    math_016.name = "Math.016"
    math_016.hide = True
    math_016.operation = 'ADD'
    math_016.use_clamp = False

    #node Reroute.001
    reroute_001 = super_fx.nodes.new("NodeReroute")
    reroute_001.name = "Reroute.001"
    #node Reroute.002
    reroute_002 = super_fx.nodes.new("NodeReroute")
    reroute_002.name = "Reroute.002"
    #node Math.008
    math_008 = super_fx.nodes.new("ShaderNodeMath")
    math_008.name = "Math.008"
    math_008.hide = True
    math_008.operation = 'ADD'
    math_008.use_clamp = False

    #node Math.010
    math_010 = super_fx.nodes.new("ShaderNodeMath")
    math_010.name = "Math.010"
    math_010.hide = True
    math_010.operation = 'ADD'
    math_010.use_clamp = False

    #node Map Range
    map_range = super_fx.nodes.new("ShaderNodeMapRange")
    map_range.name = "Map Range"
    map_range.clamp = True
    map_range.data_type = 'FLOAT'
    map_range.interpolation_type = 'LINEAR'
    #From Min
    map_range.inputs[1].default_value = -1.0
    #From Max
    map_range.inputs[2].default_value = 1.0
    #To Min
    map_range.inputs[3].default_value = 0.0
    #To Max
    map_range.inputs[4].default_value = 1.0

    #node Math
    math = super_fx.nodes.new("ShaderNodeMath")
    math.name = "Math"
    math.hide = True
    math.operation = 'COMPARE'
    math.use_clamp = False
    #Value_001
    math.inputs[1].default_value = 0.1428571492433548
    #Value_002
    math.inputs[2].default_value = 0.05000000074505806

    #node Math.003
    math_003 = super_fx.nodes.new("ShaderNodeMath")
    math_003.name = "Math.003"
    math_003.hide = True
    math_003.operation = 'COMPARE'
    math_003.use_clamp = False
    #Value_001
    math_003.inputs[1].default_value = 0.5714285969734192
    #Value_002
    math_003.inputs[2].default_value = 0.05000000074505806

    #node Math.001
    math_001 = super_fx.nodes.new("ShaderNodeMath")
    math_001.name = "Math.001"
    math_001.hide = True
    math_001.operation = 'COMPARE'
    math_001.use_clamp = False
    #Value_001
    math_001.inputs[1].default_value = 0.2857142984867096
    #Value_002
    math_001.inputs[2].default_value = 0.05000000074505806

    #node Math.002
    math_002 = super_fx.nodes.new("ShaderNodeMath")
    math_002.name = "Math.002"
    math_002.hide = True
    math_002.operation = 'COMPARE'
    math_002.use_clamp = False
    #Value_001
    math_002.inputs[1].default_value = 0.4285714328289032
    #Value_002
    math_002.inputs[2].default_value = 0.05000000074505806

    #node Math.004
    math_004 = super_fx.nodes.new("ShaderNodeMath")
    math_004.name = "Math.004"
    math_004.hide = True
    math_004.operation = 'COMPARE'
    math_004.use_clamp = False
    #Value_001
    math_004.inputs[1].default_value = 0.7142857313156128
    #Value_002
    math_004.inputs[2].default_value = 0.05000000074505806

    #node Math.005
    math_005 = super_fx.nodes.new("ShaderNodeMath")
    math_005.name = "Math.005"
    math_005.hide = True
    math_005.operation = 'COMPARE'
    math_005.use_clamp = False
    #Value_001
    math_005.inputs[1].default_value = 0.8571428656578064
    #Value_002
    math_005.inputs[2].default_value = 0.05000000074505806

    #node Reroute.005
    reroute_005 = super_fx.nodes.new("NodeReroute")
    reroute_005.name = "Reroute.005"
    #node Reroute.006
    reroute_006 = super_fx.nodes.new("NodeReroute")
    reroute_006.name = "Reroute.006"
    #node Math.006
    math_006 = super_fx.nodes.new("ShaderNodeMath")
    math_006.name = "Math.006"
    math_006.hide = True
    math_006.operation = 'COMPARE'
    math_006.use_clamp = False
    #Value_001
    math_006.inputs[1].default_value = 1.0
    #Value_002
    math_006.inputs[2].default_value = 0.05000000074505806

    #node Reroute.003
    reroute_003 = super_fx.nodes.new("NodeReroute")
    reroute_003.name = "Reroute.003"
    #node Reroute.004
    reroute_004 = super_fx.nodes.new("NodeReroute")
    reroute_004.name = "Reroute.004"
    #node Math.009
    math_009 = super_fx.nodes.new("ShaderNodeMath")
    math_009.name = "Math.009"
    math_009.hide = True
    math_009.operation = 'ADD'
    math_009.use_clamp = False

    #node Mix.001
    mix_001 = super_fx.nodes.new("ShaderNodeMix")
    mix_001.name = "Mix.001"
    mix_001.blend_type = 'MIX'
    mix_001.clamp_factor = True
    mix_001.clamp_result = False
    mix_001.data_type = 'RGBA'
    mix_001.factor_mode = 'UNIFORM'

    #node Geometry
    geometry = super_fx.nodes.new("ShaderNodeNewGeometry")
    geometry.name = "Geometry"

    #node Texture Coordinate
    texture_coordinate = super_fx.nodes.new("ShaderNodeTexCoord")
    texture_coordinate.name = "Texture Coordinate"
    texture_coordinate.from_instancer = False

    #node Separate XYZ.001
    separate_xyz_001 = super_fx.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz_001.name = "Separate XYZ.001"

    #node Math.012
    math_012 = super_fx.nodes.new("ShaderNodeMath")
    math_012.name = "Math.012"
    math_012.operation = 'MULTIPLY'
    math_012.use_clamp = False

    #node Math.011
    math_011 = super_fx.nodes.new("ShaderNodeMath")
    math_011.name = "Math.011"
    math_011.operation = 'MULTIPLY'
    math_011.use_clamp = False

    #node Separate XYZ
    separate_xyz = super_fx.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz.name = "Separate XYZ"

    #node Vector Rotate
    vector_rotate = super_fx.nodes.new("ShaderNodeVectorRotate")
    vector_rotate.name = "Vector Rotate"
    vector_rotate.invert = False
    vector_rotate.rotation_type = 'AXIS_ANGLE'
    #Center
    vector_rotate.inputs[1].default_value = (0.0, 0.0, 0.0)
    #Axis
    vector_rotate.inputs[2].default_value = (0.0, 0.0, 1.0)

    #node Mix.007
    mix_007 = super_fx.nodes.new("ShaderNodeMix")
    mix_007.name = "Mix.007"
    mix_007.blend_type = 'MIX'
    mix_007.clamp_factor = True
    mix_007.clamp_result = False
    mix_007.data_type = 'RGBA'
    mix_007.factor_mode = 'UNIFORM'

    #node Reroute.012
    reroute_012 = super_fx.nodes.new("NodeReroute")
    reroute_012.name = "Reroute.012"
    #node Reroute.013
    reroute_013 = super_fx.nodes.new("NodeReroute")
    reroute_013.name = "Reroute.013"
    #node Mix.005
    mix_005 = super_fx.nodes.new("ShaderNodeMix")
    mix_005.name = "Mix.005"
    mix_005.blend_type = 'MIX'
    mix_005.clamp_factor = True
    mix_005.clamp_result = False
    mix_005.data_type = 'RGBA'
    mix_005.factor_mode = 'UNIFORM'

    #node Mix.002
    mix_002 = super_fx.nodes.new("ShaderNodeMix")
    mix_002.name = "Mix.002"
    mix_002.blend_type = 'MIX'
    mix_002.clamp_factor = True
    mix_002.clamp_result = False
    mix_002.data_type = 'RGBA'
    mix_002.factor_mode = 'UNIFORM'

    #node Mix.003
    mix_003 = super_fx.nodes.new("ShaderNodeMix")
    mix_003.name = "Mix.003"
    mix_003.blend_type = 'MIX'
    mix_003.clamp_factor = True
    mix_003.clamp_result = False
    mix_003.data_type = 'RGBA'
    mix_003.factor_mode = 'UNIFORM'
    #A_Color
    mix_003.inputs[6].default_value = (0.0, 0.0, 0.0, 1.0)

    #node Mix.004
    mix_004 = super_fx.nodes.new("ShaderNodeMix")
    mix_004.name = "Mix.004"
    mix_004.blend_type = 'MIX'
    mix_004.clamp_factor = True
    mix_004.clamp_result = False
    mix_004.data_type = 'RGBA'
    mix_004.factor_mode = 'UNIFORM'

    #node ColorRamp
    colorramp = super_fx.nodes.new("ShaderNodeValToRGB")
    colorramp.name = "ColorRamp"
    colorramp.hide = True
    colorramp.color_ramp.color_mode = 'RGB'
    colorramp.color_ramp.hue_interpolation = 'NEAR'
    colorramp.color_ramp.interpolation = 'CONSTANT'

    #initialize color ramp elements
    colorramp.color_ramp.elements.remove(colorramp.color_ramp.elements[0])
    colorramp_cre_0 = colorramp.color_ramp.elements[0]
    colorramp_cre_0.position = 0.0
    colorramp_cre_0.alpha = 1.0
    colorramp_cre_0.color = (0.4178851246833801, 0.02121901698410511, 0.0, 1.0)

    colorramp_cre_1 = colorramp.color_ramp.elements.new(0.25)
    colorramp_cre_1.alpha = 1.0
    colorramp_cre_1.color = (0.9301111102104187, 0.11953844130039215, 0.015208516269922256, 1.0)

    colorramp_cre_2 = colorramp.color_ramp.elements.new(0.5)
    colorramp_cre_2.alpha = 1.0
    colorramp_cre_2.color = (1.0000001192092896, 0.46778395771980286, 0.03071345016360283, 1.0)

    colorramp_cre_3 = colorramp.color_ramp.elements.new(0.75)
    colorramp_cre_3.alpha = 1.0
    colorramp_cre_3.color = (1.0000001192092896, 0.7379106283187866, 0.10224173218011856, 1.0)


    #node ColorRamp.001
    colorramp_001 = super_fx.nodes.new("ShaderNodeValToRGB")
    colorramp_001.name = "ColorRamp.001"
    colorramp_001.hide = True
    colorramp_001.color_ramp.color_mode = 'RGB'
    colorramp_001.color_ramp.hue_interpolation = 'NEAR'
    colorramp_001.color_ramp.interpolation = 'CONSTANT'

    #initialize color ramp elements
    colorramp_001.color_ramp.elements.remove(colorramp_001.color_ramp.elements[0])
    colorramp_001_cre_0 = colorramp_001.color_ramp.elements[0]
    colorramp_001_cre_0.position = 0.0
    colorramp_001_cre_0.alpha = 1.0
    colorramp_001_cre_0.color = (0.1428571492433548, 0.1428571492433548, 0.1428571492433548, 1.0)

    colorramp_001_cre_1 = colorramp_001.color_ramp.elements.new(0.1428571343421936)
    colorramp_001_cre_1.alpha = 1.0
    colorramp_001_cre_1.color = (0.2857142984867096, 0.2857142984867096, 0.2857142984867096, 1.0)

    colorramp_001_cre_2 = colorramp_001.color_ramp.elements.new(0.2857142686843872)
    colorramp_001_cre_2.alpha = 1.0
    colorramp_001_cre_2.color = (0.4285714328289032, 0.4285714328289032, 0.4285714328289032, 1.0)

    colorramp_001_cre_3 = colorramp_001.color_ramp.elements.new(0.4285714626312256)
    colorramp_001_cre_3.alpha = 1.0
    colorramp_001_cre_3.color = (0.5714285969734192, 0.5714285969734192, 0.5714285969734192, 1.0)

    colorramp_001_cre_4 = colorramp_001.color_ramp.elements.new(0.5714285969734192)
    colorramp_001_cre_4.alpha = 1.0
    colorramp_001_cre_4.color = (0.7142857313156128, 0.7142857313156128, 0.7142857313156128, 1.0)

    colorramp_001_cre_5 = colorramp_001.color_ramp.elements.new(0.7142857313156128)
    colorramp_001_cre_5.alpha = 1.0
    colorramp_001_cre_5.color = (0.8571428656578064, 0.8571428656578064, 0.8571428656578064, 1.0)

    colorramp_001_cre_6 = colorramp_001.color_ramp.elements.new(0.8571428656578064)
    colorramp_001_cre_6.alpha = 1.0
    colorramp_001_cre_6.color = (1.0, 1.0, 1.0, 1.0)


    #node Mix
    mix = super_fx.nodes.new("ShaderNodeMix")
    mix.name = "Mix"
    mix.blend_type = 'MIX'
    mix.clamp_factor = True
    mix.clamp_result = False
    mix.data_type = 'RGBA'
    mix.factor_mode = 'UNIFORM'

    #node Reroute.014
    reroute_014 = super_fx.nodes.new("NodeReroute")
    reroute_014.name = "Reroute.014"
    #node Map Range.003
    map_range_003 = super_fx.nodes.new("ShaderNodeMapRange")
    map_range_003.name = "Map Range.003"
    map_range_003.hide = True
    map_range_003.clamp = True
    map_range_003.data_type = 'FLOAT'
    map_range_003.interpolation_type = 'LINEAR'
    #From Min
    map_range_003.inputs[1].default_value = 0.5
    #From Max
    map_range_003.inputs[2].default_value = 0.5001000165939331
    #To Min
    map_range_003.inputs[3].default_value = 0.0
    #To Max
    map_range_003.inputs[4].default_value = 1.0

    #node Map Range.002
    map_range_002 = super_fx.nodes.new("ShaderNodeMapRange")
    map_range_002.name = "Map Range.002"
    map_range_002.hide = True
    map_range_002.clamp = True
    map_range_002.data_type = 'FLOAT'
    map_range_002.interpolation_type = 'LINEAR'
    #From Min
    map_range_002.inputs[1].default_value = 0.5
    #From Max
    map_range_002.inputs[2].default_value = 0.5001000165939331
    #To Min
    map_range_002.inputs[3].default_value = 0.0
    #To Max
    map_range_002.inputs[4].default_value = 1.0

    #node Mix.010
    mix_010 = super_fx.nodes.new("ShaderNodeMix")
    mix_010.name = "Mix.010"
    mix_010.hide = True
    mix_010.blend_type = 'MIX'
    mix_010.clamp_factor = True
    mix_010.clamp_result = False
    mix_010.data_type = 'RGBA'
    mix_010.factor_mode = 'UNIFORM'

    #node Group Input
    group_input = super_fx.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"
    #super_fx inputs
    #input Colour 1
    super_fx.inputs.new('NodeSocketColor', "Colour 1")
    super_fx.inputs[0].default_value = (0.4178851246833801, 0.02121901698410511, 0.0, 1.0)
    super_fx.inputs[0].attribute_domain = 'POINT'

    #input Colour 2
    super_fx.inputs.new('NodeSocketColor', "Colour 2")
    super_fx.inputs[1].default_value = (0.9301111102104187, 0.11953844130039215, 0.015208516269922256, 1.0)
    super_fx.inputs[1].attribute_domain = 'POINT'

    #input Colour 3
    super_fx.inputs.new('NodeSocketColor', "Colour 3")
    super_fx.inputs[2].default_value = (1.0000001192092896, 0.46778395771980286, 0.03071345016360283, 1.0)
    super_fx.inputs[2].attribute_domain = 'POINT'

    #input Colour 4
    super_fx.inputs.new('NodeSocketColor', "Colour 4")
    super_fx.inputs[3].default_value = (1.0000001192092896, 0.7379106283187866, 0.10224173218011856, 1.0)
    super_fx.inputs[3].attribute_domain = 'POINT'

    #input Dither
    super_fx.inputs.new('NodeSocketFloat', "Dither")
    super_fx.inputs[4].default_value = 96.18470001220703
    super_fx.inputs[4].min_value = 0.0
    super_fx.inputs[4].max_value = 10000.0
    super_fx.inputs[4].attribute_domain = 'POINT'

    #input Aspect X
    super_fx.inputs.new('NodeSocketFloat', "Aspect X")
    super_fx.inputs[5].default_value = 8.0
    super_fx.inputs[5].min_value = 1.0
    super_fx.inputs[5].max_value = 100.0
    super_fx.inputs[5].attribute_domain = 'POINT'

    #input Aspect Y
    super_fx.inputs.new('NodeSocketFloat', "Aspect Y")
    super_fx.inputs[6].default_value = 7.0
    super_fx.inputs[6].min_value = 1.0
    super_fx.inputs[6].max_value = 100.0
    super_fx.inputs[6].attribute_domain = 'POINT'

    #input Angle
    super_fx.inputs.new('NodeSocketFloatAngle', "Angle")
    super_fx.inputs[7].default_value = 0.0
    super_fx.inputs[7].min_value = 0.0
    super_fx.inputs[7].max_value = 3.4028234663852886e+38
    super_fx.inputs[7].attribute_domain = 'POINT'

    #input Dither 1
    super_fx.inputs.new('NodeSocketFloatFactor', "Dither 1")
    super_fx.inputs[8].default_value = 0.0
    super_fx.inputs[8].min_value = 0.0
    super_fx.inputs[8].max_value = 1.0
    super_fx.inputs[8].attribute_domain = 'POINT'

    #input Dither 2
    super_fx.inputs.new('NodeSocketFloatFactor', "Dither 2")
    super_fx.inputs[9].default_value = 0.0
    super_fx.inputs[9].min_value = 0.0
    super_fx.inputs[9].max_value = 1.0
    super_fx.inputs[9].attribute_domain = 'POINT'

    #input Dither 3
    super_fx.inputs.new('NodeSocketFloatFactor', "Dither 3")
    super_fx.inputs[10].default_value = 0.0
    super_fx.inputs[10].min_value = 0.0
    super_fx.inputs[10].max_value = 1.0
    super_fx.inputs[10].attribute_domain = 'POINT'

    #input Dither 4
    super_fx.inputs.new('NodeSocketFloatFactor', "Dither 4")
    super_fx.inputs[11].default_value = 0.0
    super_fx.inputs[11].min_value = 0.0
    super_fx.inputs[11].max_value = 1.0
    super_fx.inputs[11].attribute_domain = 'POINT'

    #input Carry Over
    super_fx.inputs.new('NodeSocketFloatFactor', "Carry Over")
    super_fx.inputs[12].default_value = 0.0
    super_fx.inputs[12].min_value = 0.0
    super_fx.inputs[12].max_value = 1.0
    super_fx.inputs[12].attribute_domain = 'POINT'



    #node Mix.009
    mix_009 = super_fx.nodes.new("ShaderNodeMix")
    mix_009.name = "Mix.009"
    mix_009.hide = True
    mix_009.blend_type = 'MIX'
    mix_009.clamp_factor = True
    mix_009.clamp_result = False
    mix_009.data_type = 'RGBA'
    mix_009.factor_mode = 'UNIFORM'

    #node Reroute.019
    reroute_019 = super_fx.nodes.new("NodeReroute")
    reroute_019.name = "Reroute.019"
    #node Combine XYZ
    combine_xyz = super_fx.nodes.new("ShaderNodeCombineXYZ")
    combine_xyz.name = "Combine XYZ"
    #Z
    combine_xyz.inputs[2].default_value = 0.0

    #node Reroute.018
    reroute_018 = super_fx.nodes.new("NodeReroute")
    reroute_018.name = "Reroute.018"
    #node Checker Texture.001
    checker_texture_001 = super_fx.nodes.new("ShaderNodeTexChecker")
    checker_texture_001.name = "Checker Texture.001"
    checker_texture_001.hide = True

    #node Checker Texture.002
    checker_texture_002 = super_fx.nodes.new("ShaderNodeTexChecker")
    checker_texture_002.name = "Checker Texture.002"
    checker_texture_002.hide = True

    #node Reroute.017
    reroute_017 = super_fx.nodes.new("NodeReroute")
    reroute_017.name = "Reroute.017"
    #node Reroute.010
    reroute_010 = super_fx.nodes.new("NodeReroute")
    reroute_010.name = "Reroute.010"
    #node Checker Texture.003
    checker_texture_003 = super_fx.nodes.new("ShaderNodeTexChecker")
    checker_texture_003.name = "Checker Texture.003"
    checker_texture_003.hide = True

    #node Mix.008
    mix_008 = super_fx.nodes.new("ShaderNodeMix")
    mix_008.name = "Mix.008"
    mix_008.hide = True
    mix_008.blend_type = 'MIX'
    mix_008.clamp_factor = True
    mix_008.clamp_result = False
    mix_008.data_type = 'RGBA'
    mix_008.factor_mode = 'UNIFORM'

    #node Mix.011
    mix_011 = super_fx.nodes.new("ShaderNodeMix")
    mix_011.name = "Mix.011"
    mix_011.hide = True
    mix_011.blend_type = 'MIX'
    mix_011.clamp_factor = True
    mix_011.clamp_result = False
    mix_011.data_type = 'RGBA'
    mix_011.factor_mode = 'UNIFORM'

    #node Mix.012
    mix_012 = super_fx.nodes.new("ShaderNodeMix")
    mix_012.name = "Mix.012"
    mix_012.hide = True
    mix_012.blend_type = 'MIX'
    mix_012.clamp_factor = True
    mix_012.clamp_result = False
    mix_012.data_type = 'RGBA'
    mix_012.factor_mode = 'UNIFORM'

    #node Reroute.009
    reroute_009 = super_fx.nodes.new("NodeReroute")
    reroute_009.name = "Reroute.009"
    #node Reroute.008
    reroute_008 = super_fx.nodes.new("NodeReroute")
    reroute_008.name = "Reroute.008"
    #node Reroute.007
    reroute_007 = super_fx.nodes.new("NodeReroute")
    reroute_007.name = "Reroute.007"
    #node Reroute.011
    reroute_011 = super_fx.nodes.new("NodeReroute")
    reroute_011.name = "Reroute.011"
    #node Math.013
    math_013 = super_fx.nodes.new("ShaderNodeMath")
    math_013.name = "Math.013"
    math_013.hide = True
    math_013.operation = 'ADD'
    math_013.use_clamp = False

    #node Math.014
    math_014 = super_fx.nodes.new("ShaderNodeMath")
    math_014.name = "Math.014"
    math_014.hide = True
    math_014.operation = 'ADD'
    math_014.use_clamp = False

    #node Math.015
    math_015 = super_fx.nodes.new("ShaderNodeMath")
    math_015.name = "Math.015"
    math_015.hide = True
    math_015.operation = 'ADD'
    math_015.use_clamp = False

    #node Reroute.016
    reroute_016 = super_fx.nodes.new("NodeReroute")
    reroute_016.name = "Reroute.016"
    #node Reroute.020
    reroute_020 = super_fx.nodes.new("NodeReroute")
    reroute_020.name = "Reroute.020"

    #Set locations
    group_output.location = (2282.842529296875, 465.82562255859375)
    mix_006.location = (1908.984130859375, 608.59033203125)
    reroute.location = (453.58441162109375, 634.654296875)
    math_007.location = (482.52679443359375, 636.1538696289062)
    map_range_001.location = (-398.2610168457031, -779.6416015625)
    reroute_015.location = (-972.3839721679688, -793.5418701171875)
    map_range_004.location = (-414.8504333496094, -852.0895385742188)
    map_range_005.location = (-807.3466186523438, -953.5443725585938)
    math_016.location = (-881.3363037109375, -803.5853881835938)
    reroute_001.location = (452.563232421875, 606.0347900390625)
    reroute_002.location = (452.563232421875, 580.4816284179688)
    math_008.location = (476.9945068359375, 581.4722290039062)
    math_010.location = (720.0384521484375, 586.5828857421875)
    map_range.location = (-535.328369140625, 383.47430419921875)
    math.location = (71.72320556640625, 434.61175537109375)
    math_003.location = (65.544677734375, 285.2316589355469)
    math_001.location = (67.628662109375, 379.29876708984375)
    math_002.location = (69.14462280273438, 333.404052734375)
    math_004.location = (63.43743896484375, 225.01170349121094)
    math_005.location = (64.84713745117188, 163.89540100097656)
    reroute_005.location = (455.62677001953125, 496.66741943359375)
    reroute_006.location = (457.66912841796875, 463.95941162109375)
    math_006.location = (66.68914794921875, 110.44473266601562)
    reroute_003.location = (452.563232421875, 554.9285278320312)
    reroute_004.location = (454.6055908203125, 528.353271484375)
    math_009.location = (474.919921875, 524.714111328125)
    mix_001.location = (394.3155517578125, 138.9174041748047)
    geometry.location = (-1391.2242431640625, 475.33050537109375)
    texture_coordinate.location = (-1650.353515625, 301.2451171875)
    separate_xyz_001.location = (-1426.4466552734375, 133.83160400390625)
    math_012.location = (-1206.5218505859375, 145.19619750976562)
    math_011.location = (-1208.5938720703125, -17.931964874267578)
    separate_xyz.location = (-913.7718505859375, 347.81878662109375)
    vector_rotate.location = (-1133.9017333984375, 489.4241943359375)
    mix_007.location = (739.2387084960938, -153.19009399414062)
    reroute_012.location = (577.0045166015625, -762.3526000976562)
    reroute_013.location = (-952.0925903320312, -638.2490234375)
    mix_005.location = (980.8947143554688, 156.4751739501953)
    mix_002.location = (485.20977783203125, -126.27940368652344)
    mix_003.location = (392.2557373046875, -394.29913330078125)
    mix_004.location = (901.0579833984375, 455.58966064453125)
    colorramp.location = (-316.13818359375, 533.0762939453125)
    colorramp_001.location = (-296.5804748535156, 420.1319580078125)
    mix.location = (393.44183349609375, 375.91888427734375)
    reroute_014.location = (-956.8670043945312, -706.3385620117188)
    map_range_003.location = (-476.3591003417969, -552.4315185546875)
    map_range_002.location = (-379.5137023925781, -673.34765625)
    mix_010.location = (260.29583740234375, -299.2886962890625)
    group_input.location = (-1648.4683837890625, -225.02638244628906)
    mix_009.location = (5.363819122314453, -107.00849914550781)
    reroute_019.location = (-551.6076049804688, -419.2662353515625)
    combine_xyz.location = (-986.8905029296875, 143.31533813476562)
    reroute_018.location = (-554.6715087890625, -270.03729248046875)
    checker_texture_001.location = (-329.90240478515625, -276.86334228515625)
    checker_texture_002.location = (-248.88433837890625, -371.6480712890625)
    reroute_017.location = (-555.7195434570312, -148.13616943359375)
    reroute_010.location = (-593.1959838867188, -444.0399475097656)
    checker_texture_003.location = (-336.94207763671875, -151.83419799804688)
    mix_008.location = (-174.41075134277344, 160.50559997558594)
    mix_011.location = (-469.5552978515625, -219.6685028076172)
    mix_012.location = (-463.43829345703125, -343.8554382324219)
    reroute_009.location = (-583.4044799804688, -331.49444580078125)
    reroute_008.location = (-579.0795288085938, -227.7291259765625)
    reroute_007.location = (-551.5709228515625, -109.60428619384766)
    reroute_011.location = (-948.509765625, -554.630615234375)
    math_013.location = (-830.0120849609375, -522.86865234375)
    math_014.location = (-841.9479370117188, -635.1553344726562)
    math_015.location = (-855.077392578125, -710.4113159179688)
    reroute_016.location = (-994.7044067382812, -880.1026611328125)
    reroute_020.location = (-575.075439453125, 72.70051574707031)

    #Set dimensions
    group_output.width, group_output.height = 140.0, 100.0
    mix_006.width, mix_006.height = 140.0, 100.0
    reroute.width, reroute.height = 16.0, 100.0
    math_007.width, math_007.height = 140.0, 100.0
    map_range_001.width, map_range_001.height = 140.0, 100.0
    reroute_015.width, reroute_015.height = 16.0, 100.0
    map_range_004.width, map_range_004.height = 140.0, 100.0
    map_range_005.width, map_range_005.height = 140.0, 100.0
    math_016.width, math_016.height = 140.0, 100.0
    reroute_001.width, reroute_001.height = 16.0, 100.0
    reroute_002.width, reroute_002.height = 16.0, 100.0
    math_008.width, math_008.height = 140.0, 100.0
    math_010.width, math_010.height = 140.0, 100.0
    map_range.width, map_range.height = 140.0, 100.0
    math.width, math.height = 140.0, 100.0
    math_003.width, math_003.height = 140.0, 100.0
    math_001.width, math_001.height = 140.0, 100.0
    math_002.width, math_002.height = 140.0, 100.0
    math_004.width, math_004.height = 140.0, 100.0
    math_005.width, math_005.height = 140.0, 100.0
    reroute_005.width, reroute_005.height = 16.0, 100.0
    reroute_006.width, reroute_006.height = 16.0, 100.0
    math_006.width, math_006.height = 140.0, 100.0
    reroute_003.width, reroute_003.height = 16.0, 100.0
    reroute_004.width, reroute_004.height = 16.0, 100.0
    math_009.width, math_009.height = 140.0, 100.0
    mix_001.width, mix_001.height = 134.33251953125, 100.0
    geometry.width, geometry.height = 140.0, 100.0
    texture_coordinate.width, texture_coordinate.height = 140.0, 100.0
    separate_xyz_001.width, separate_xyz_001.height = 140.0, 100.0
    math_012.width, math_012.height = 140.0, 100.0
    math_011.width, math_011.height = 140.0, 100.0
    separate_xyz.width, separate_xyz.height = 140.0, 100.0
    vector_rotate.width, vector_rotate.height = 140.0, 100.0
    mix_007.width, mix_007.height = 140.0, 100.0
    reroute_012.width, reroute_012.height = 16.0, 100.0
    reroute_013.width, reroute_013.height = 16.0, 100.0
    mix_005.width, mix_005.height = 140.0, 100.0
    mix_002.width, mix_002.height = 134.33251953125, 100.0
    mix_003.width, mix_003.height = 134.33251953125, 100.0
    mix_004.width, mix_004.height = 140.0, 100.0
    colorramp.width, colorramp.height = 240.0, 100.0
    colorramp_001.width, colorramp_001.height = 240.0, 100.0
    mix.width, mix.height = 134.33251953125, 100.0
    reroute_014.width, reroute_014.height = 16.0, 100.0
    map_range_003.width, map_range_003.height = 140.0, 100.0
    map_range_002.width, map_range_002.height = 140.0, 100.0
    mix_010.width, mix_010.height = 134.33251953125, 100.0
    group_input.width, group_input.height = 140.0, 100.0
    mix_009.width, mix_009.height = 134.33251953125, 100.0
    reroute_019.width, reroute_019.height = 16.0, 100.0
    combine_xyz.width, combine_xyz.height = 140.0, 100.0
    reroute_018.width, reroute_018.height = 16.0, 100.0
    checker_texture_001.width, checker_texture_001.height = 140.0, 100.0
    checker_texture_002.width, checker_texture_002.height = 140.0, 100.0
    reroute_017.width, reroute_017.height = 16.0, 100.0
    reroute_010.width, reroute_010.height = 16.0, 100.0
    checker_texture_003.width, checker_texture_003.height = 140.0, 100.0
    mix_008.width, mix_008.height = 134.33251953125, 100.0
    mix_011.width, mix_011.height = 134.33251953125, 100.0
    mix_012.width, mix_012.height = 134.33251953125, 100.0
    reroute_009.width, reroute_009.height = 16.0, 100.0
    reroute_008.width, reroute_008.height = 16.0, 100.0
    reroute_007.width, reroute_007.height = 16.0, 100.0
    reroute_011.width, reroute_011.height = 16.0, 100.0
    math_013.width, math_013.height = 140.0, 100.0
    math_014.width, math_014.height = 140.0, 100.0
    math_015.width, math_015.height = 140.0, 100.0
    reroute_016.width, reroute_016.height = 16.0, 100.0
    reroute_020.width, reroute_020.height = 16.0, 100.0

    #initialize super_fx links
    #vector_rotate.Vector -> separate_xyz.Vector
    super_fx.links.new(vector_rotate.outputs[0], separate_xyz.inputs[0])
    #separate_xyz.X -> map_range.Value
    super_fx.links.new(separate_xyz.outputs[0], map_range.inputs[0])
    #map_range.Result -> colorramp.Fac
    super_fx.links.new(map_range.outputs[0], colorramp.inputs[0])
    #map_range.Result -> colorramp_001.Fac
    super_fx.links.new(map_range.outputs[0], colorramp_001.inputs[0])
    #colorramp_001.Color -> math.Value
    super_fx.links.new(colorramp_001.outputs[0], math.inputs[0])
    #colorramp_001.Color -> math_001.Value
    super_fx.links.new(colorramp_001.outputs[0], math_001.inputs[0])
    #colorramp_001.Color -> math_002.Value
    super_fx.links.new(colorramp_001.outputs[0], math_002.inputs[0])
    #colorramp_001.Color -> math_003.Value
    super_fx.links.new(colorramp_001.outputs[0], math_003.inputs[0])
    #colorramp_001.Color -> math_004.Value
    super_fx.links.new(colorramp_001.outputs[0], math_004.inputs[0])
    #colorramp_001.Color -> math_005.Value
    super_fx.links.new(colorramp_001.outputs[0], math_005.inputs[0])
    #colorramp_001.Color -> math_006.Value
    super_fx.links.new(colorramp_001.outputs[0], math_006.inputs[0])
    #math.Value -> mix.Factor
    super_fx.links.new(math.outputs[0], mix.inputs[0])
    #math_002.Value -> mix_001.Factor
    super_fx.links.new(math_002.outputs[0], mix_001.inputs[0])
    #math_004.Value -> mix_002.Factor
    super_fx.links.new(math_004.outputs[0], mix_002.inputs[0])
    #math_006.Value -> mix_003.Factor
    super_fx.links.new(math_006.outputs[0], mix_003.inputs[0])
    #checker_texture_003.Color -> mix.A
    super_fx.links.new(checker_texture_003.outputs[0], mix.inputs[6])
    #checker_texture_001.Color -> mix_001.A
    super_fx.links.new(checker_texture_001.outputs[0], mix_001.inputs[6])
    #checker_texture_002.Color -> mix_002.A
    super_fx.links.new(checker_texture_002.outputs[0], mix_002.inputs[6])
    #math.Value -> reroute.Input
    super_fx.links.new(math.outputs[0], reroute.inputs[0])
    #math_001.Value -> reroute_001.Input
    super_fx.links.new(math_001.outputs[0], reroute_001.inputs[0])
    #math_002.Value -> reroute_002.Input
    super_fx.links.new(math_002.outputs[0], reroute_002.inputs[0])
    #math_003.Value -> reroute_003.Input
    super_fx.links.new(math_003.outputs[0], reroute_003.inputs[0])
    #math_004.Value -> reroute_004.Input
    super_fx.links.new(math_004.outputs[0], reroute_004.inputs[0])
    #math_005.Value -> reroute_005.Input
    super_fx.links.new(math_005.outputs[0], reroute_005.inputs[0])
    #math_006.Value -> reroute_006.Input
    super_fx.links.new(math_006.outputs[0], reroute_006.inputs[0])
    #reroute.Output -> math_007.Value
    super_fx.links.new(reroute.outputs[0], math_007.inputs[0])
    #reroute_001.Output -> math_007.Value
    super_fx.links.new(reroute_001.outputs[0], math_007.inputs[1])
    #reroute_002.Output -> math_008.Value
    super_fx.links.new(reroute_002.outputs[0], math_008.inputs[0])
    #reroute_003.Output -> math_008.Value
    super_fx.links.new(reroute_003.outputs[0], math_008.inputs[1])
    #reroute_004.Output -> math_009.Value
    super_fx.links.new(reroute_004.outputs[0], math_009.inputs[0])
    #reroute_005.Output -> math_009.Value
    super_fx.links.new(reroute_005.outputs[0], math_009.inputs[1])
    #math_007.Value -> mix_004.Factor
    super_fx.links.new(math_007.outputs[0], mix_004.inputs[0])
    #mix_002.Result -> mix_005.B
    super_fx.links.new(mix_002.outputs[2], mix_005.inputs[7])
    #math_009.Value -> mix_005.Factor
    super_fx.links.new(math_009.outputs[0], mix_005.inputs[0])
    #mix_005.Result -> mix_006.A
    super_fx.links.new(mix_005.outputs[2], mix_006.inputs[6])
    #math_007.Value -> math_010.Value
    super_fx.links.new(math_007.outputs[0], math_010.inputs[0])
    #math_010.Value -> mix_006.Factor
    super_fx.links.new(math_010.outputs[0], mix_006.inputs[0])
    #math_008.Value -> math_010.Value
    super_fx.links.new(math_008.outputs[0], math_010.inputs[1])
    #group_input.Colour 1 -> reroute_007.Input
    super_fx.links.new(group_input.outputs[0], reroute_007.inputs[0])
    #group_input.Colour 2 -> reroute_008.Input
    super_fx.links.new(group_input.outputs[1], reroute_008.inputs[0])
    #group_input.Colour 3 -> reroute_009.Input
    super_fx.links.new(group_input.outputs[2], reroute_009.inputs[0])
    #group_input.Colour 4 -> reroute_010.Input
    super_fx.links.new(group_input.outputs[3], reroute_010.inputs[0])
    #reroute_007.Output -> checker_texture_003.Color1
    super_fx.links.new(reroute_007.outputs[0], checker_texture_003.inputs[1])
    #reroute_008.Output -> checker_texture_003.Color2
    super_fx.links.new(reroute_008.outputs[0], checker_texture_003.inputs[2])
    #mix_009.Result -> mix_001.B
    super_fx.links.new(mix_009.outputs[2], mix_001.inputs[7])
    #reroute_009.Output -> checker_texture_001.Color2
    super_fx.links.new(reroute_009.outputs[0], checker_texture_001.inputs[2])
    #mix_010.Result -> mix_002.B
    super_fx.links.new(mix_010.outputs[2], mix_002.inputs[7])
    #mix_012.Result -> checker_texture_002.Color1
    super_fx.links.new(mix_012.outputs[2], checker_texture_002.inputs[1])
    #reroute_010.Output -> checker_texture_002.Color2
    super_fx.links.new(reroute_010.outputs[0], checker_texture_002.inputs[2])
    #reroute_010.Output -> mix_003.B
    super_fx.links.new(reroute_010.outputs[0], mix_003.inputs[7])
    #group_input.Dither -> checker_texture_003.Scale
    super_fx.links.new(group_input.outputs[4], checker_texture_003.inputs[3])
    #group_input.Dither -> checker_texture_001.Scale
    super_fx.links.new(group_input.outputs[4], checker_texture_001.inputs[3])
    #group_input.Dither -> checker_texture_002.Scale
    super_fx.links.new(group_input.outputs[4], checker_texture_002.inputs[3])
    #math_012.Value -> combine_xyz.X
    super_fx.links.new(math_012.outputs[0], combine_xyz.inputs[0])
    #math_011.Value -> combine_xyz.Y
    super_fx.links.new(math_011.outputs[0], combine_xyz.inputs[1])
    #separate_xyz_001.Y -> math_011.Value
    super_fx.links.new(separate_xyz_001.outputs[1], math_011.inputs[0])
    #separate_xyz_001.X -> math_012.Value
    super_fx.links.new(separate_xyz_001.outputs[0], math_012.inputs[0])
    #texture_coordinate.Window -> separate_xyz_001.Vector
    super_fx.links.new(texture_coordinate.outputs[5], separate_xyz_001.inputs[0])
    #group_input.Aspect X -> math_012.Value
    super_fx.links.new(group_input.outputs[5], math_012.inputs[1])
    #group_input.Aspect Y -> math_011.Value
    super_fx.links.new(group_input.outputs[6], math_011.inputs[1])
    #geometry.True Normal -> vector_rotate.Vector
    super_fx.links.new(geometry.outputs[3], vector_rotate.inputs[0])
    #group_input.Angle -> vector_rotate.Angle
    super_fx.links.new(group_input.outputs[7], vector_rotate.inputs[3])
    #mix_007.Result -> mix_005.A
    super_fx.links.new(mix_007.outputs[2], mix_005.inputs[6])
    #group_input.Dither 1 -> reroute_011.Input
    super_fx.links.new(group_input.outputs[8], reroute_011.inputs[0])
    #reroute_012.Output -> mix_007.Factor
    super_fx.links.new(reroute_012.outputs[0], mix_007.inputs[0])
    #group_input.Dither 2 -> reroute_013.Input
    super_fx.links.new(group_input.outputs[9], reroute_013.inputs[0])
    #group_input.Dither 3 -> reroute_014.Input
    super_fx.links.new(group_input.outputs[10], reroute_014.inputs[0])
    #math_015.Value -> map_range_001.Value
    super_fx.links.new(math_015.outputs[0], map_range_001.inputs[0])
    #math_013.Value -> map_range_003.Value
    super_fx.links.new(math_013.outputs[0], map_range_003.inputs[0])
    #math_014.Value -> map_range_002.Value
    super_fx.links.new(math_014.outputs[0], map_range_002.inputs[0])
    #mix_004.Result -> mix_006.B
    super_fx.links.new(mix_004.outputs[2], mix_006.inputs[7])
    #mix_001.Result -> mix_004.A
    super_fx.links.new(mix_001.outputs[2], mix_004.inputs[6])
    #mix_003.Result -> mix_007.A
    super_fx.links.new(mix_003.outputs[2], mix_007.inputs[6])
    #mix_002.Result -> mix_007.B
    super_fx.links.new(mix_002.outputs[2], mix_007.inputs[7])
    #mix.Result -> mix_004.B
    super_fx.links.new(mix.outputs[2], mix_004.inputs[7])
    #reroute_007.Output -> mix_008.A
    super_fx.links.new(reroute_007.outputs[0], mix_008.inputs[6])
    #mix_008.Result -> mix.B
    super_fx.links.new(mix_008.outputs[2], mix.inputs[7])
    #checker_texture_003.Color -> mix_008.B
    super_fx.links.new(checker_texture_003.outputs[0], mix_008.inputs[7])
    #map_range_003.Result -> mix_008.Factor
    super_fx.links.new(map_range_003.outputs[0], mix_008.inputs[0])
    #group_input.Dither 4 -> reroute_015.Input
    super_fx.links.new(group_input.outputs[11], reroute_015.inputs[0])
    #math_016.Value -> map_range_004.Value
    super_fx.links.new(math_016.outputs[0], map_range_004.inputs[0])
    #map_range_004.Result -> reroute_012.Input
    super_fx.links.new(map_range_004.outputs[0], reroute_012.inputs[0])
    #reroute_008.Output -> mix_009.A
    super_fx.links.new(reroute_008.outputs[0], mix_009.inputs[6])
    #map_range_002.Result -> mix_009.Factor
    super_fx.links.new(map_range_002.outputs[0], mix_009.inputs[0])
    #checker_texture_001.Color -> mix_009.B
    super_fx.links.new(checker_texture_001.outputs[0], mix_009.inputs[7])
    #reroute_009.Output -> mix_010.A
    super_fx.links.new(reroute_009.outputs[0], mix_010.inputs[6])
    #checker_texture_002.Color -> mix_010.B
    super_fx.links.new(checker_texture_002.outputs[0], mix_010.inputs[7])
    #map_range_001.Result -> mix_010.Factor
    super_fx.links.new(map_range_001.outputs[0], mix_010.inputs[0])
    #group_input.Carry Over -> reroute_016.Input
    super_fx.links.new(group_input.outputs[12], reroute_016.inputs[0])
    #reroute_016.Output -> map_range_005.Value
    super_fx.links.new(reroute_016.outputs[0], map_range_005.inputs[0])
    #reroute_019.Output -> checker_texture_002.Vector
    super_fx.links.new(reroute_019.outputs[0], checker_texture_002.inputs[0])
    #reroute_018.Output -> checker_texture_001.Vector
    super_fx.links.new(reroute_018.outputs[0], checker_texture_001.inputs[0])
    #reroute_017.Output -> checker_texture_003.Vector
    super_fx.links.new(reroute_017.outputs[0], checker_texture_003.inputs[0])
    #combine_xyz.Vector -> reroute_020.Input
    super_fx.links.new(combine_xyz.outputs[0], reroute_020.inputs[0])
    #reroute_020.Output -> reroute_017.Input
    super_fx.links.new(reroute_020.outputs[0], reroute_017.inputs[0])
    #reroute_017.Output -> reroute_018.Input
    super_fx.links.new(reroute_017.outputs[0], reroute_018.inputs[0])
    #reroute_018.Output -> reroute_019.Input
    super_fx.links.new(reroute_018.outputs[0], reroute_019.inputs[0])
    #mix_006.Result -> group_output.Emission
    super_fx.links.new(mix_006.outputs[2], group_output.inputs[0])
    #map_range_005.Result -> mix_011.Factor
    super_fx.links.new(map_range_005.outputs[0], mix_011.inputs[0])
    #mix_011.Result -> checker_texture_001.Color1
    super_fx.links.new(mix_011.outputs[2], checker_texture_001.inputs[1])
    #map_range_005.Result -> mix_012.Factor
    super_fx.links.new(map_range_005.outputs[0], mix_012.inputs[0])
    #reroute_007.Output -> mix_012.B
    super_fx.links.new(reroute_007.outputs[0], mix_012.inputs[7])
    #reroute_009.Output -> mix_012.A
    super_fx.links.new(reroute_009.outputs[0], mix_012.inputs[6])
    #reroute_008.Output -> mix_011.A
    super_fx.links.new(reroute_008.outputs[0], mix_011.inputs[6])
    #reroute_007.Output -> mix_011.B
    super_fx.links.new(reroute_007.outputs[0], mix_011.inputs[7])
    #reroute_011.Output -> math_013.Value
    super_fx.links.new(reroute_011.outputs[0], math_013.inputs[0])
    #reroute_013.Output -> math_014.Value
    super_fx.links.new(reroute_013.outputs[0], math_014.inputs[0])
    #reroute_014.Output -> math_015.Value
    super_fx.links.new(reroute_014.outputs[0], math_015.inputs[0])
    #reroute_015.Output -> math_016.Value
    super_fx.links.new(reroute_015.outputs[0], math_016.inputs[0])
    #reroute_016.Output -> math_016.Value
    super_fx.links.new(reroute_016.outputs[0], math_016.inputs[1])
    #reroute_016.Output -> math_015.Value
    super_fx.links.new(reroute_016.outputs[0], math_015.inputs[1])
    #reroute_016.Output -> math_014.Value
    super_fx.links.new(reroute_016.outputs[0], math_014.inputs[1])
    #reroute_016.Output -> math_013.Value
    super_fx.links.new(reroute_016.outputs[0], math_013.inputs[1])
    return super_fx

    superfx = mat.node_tree
    #start with a clean node tree
    for node in superfx.nodes:
        superfx.nodes.remove(node)
    

    #initialize superfx nodes
    #node Material Output
    material_output = superfx.nodes.new("ShaderNodeOutputMaterial")
    material_output.name = "Material Output"
    material_output.is_active_output = True
    material_output.target = 'ALL'
    #Displacement
    material_output.inputs[2].default_value = (0.0, 0.0, 0.0)

    #node Group
    group = superfx.nodes.new("ShaderNodeGroup")
    group.name = "Group"
    group.node_tree = super_fx
    #Input_1
    group.inputs[0].default_value = (0.5647116899490356, 0.623960554599762, 0.6724432706832886, 1.0)
    #Input_2
    group.inputs[1].default_value = (0.37626221776008606, 0.34191450476646423, 0.33245155215263367, 1.0)
    #Input_3
    group.inputs[2].default_value = (0.23074008524417877, 0.16513220965862274, 0.17144113779067993, 1.0)
    #Input_4
    group.inputs[3].default_value = (0.14702729880809784, 0.03954625129699707, 0.04091520607471466, 1.0)
    #Input_5
    group.inputs[4].default_value = 96.18470001220703
    #Input_6
    group.inputs[5].default_value = 8.0
    #Input_7
    group.inputs[6].default_value = 7.0
    #Input_8
    group.inputs[7].default_value = 0.0
    #Input_9
    group.inputs[8].default_value = 0.0
    #Input_10
    group.inputs[9].default_value = 0.0
    #Input_11
    group.inputs[10].default_value = 0.0
    #Input_12
    group.inputs[11].default_value = 0.0
    #Input_13
    group.inputs[12].default_value = 0.0


    #Set locations
    material_output.location = (1847.483154296875, 525.82470703125)
    group.location = (1578.4364013671875, 692.6035766601562)

    #Set dimensions
    material_output.width, material_output.height = 140.0, 100.0
    group.width, group.height = 170.5828857421875, 100.0

    #initialize superfx links
    #group.Emission -> material_output.Surface
    superfx.links.new(group.outputs[0], material_output.inputs[0])
    return superfx

class OBJECT_OT_create_super_fx(bpy.types.Operator):
    """Create the Super FX node group and base material, and set color management to Standard."""
    bl_idname = "object.create_super_fx"
    bl_label = "Create Super FX Node Group"

    def execute(self, context):
        # Call the function to create the Super FX node group
        super_fx_node_group()

        # Set render color management to Standard
        scene = context.scene
        if scene.view_settings.view_transform != "Standard":
            scene.view_settings.view_transform = "Standard"
            self.report({'INFO'}, "Render color management set to Standard")
        else:
            self.report({'INFO'}, "Render color management already set to Standard")

        self.report({'INFO'}, "Super FX node group created")
        return {'FINISHED'}


# =========================
# FastFX Menu Panel -  Palette assignment (fancy)
# =========================
class OBJECT_OT_apply_material_colors(bpy.types.Operator):
    """Apply colors and additional settings based on material names (FX#)"""
    bl_idname = "object.apply_material_colors"
    bl_label = "Apply Material Palette (Fancy)"

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "No mesh object selected")
            return {'CANCELLED'}

        if not obj.data.materials:
            self.report({'WARNING'}, "No materials found on selected object")
            return {'CANCELLED'}

        # Ensure the Super FX node group exists
        if "Super FX" not in bpy.data.node_groups:
            self.report({'WARNING'}, "No Super FX node group")
            return {'CANCELLED'}

        for material_slot in obj.material_slots:
            material = material_slot.material
            if material and (material.name.startswith("FX") or material.name.startswith("FE")):
                try:
                    # Extract color index from the material name
                    color_index = int(material.name[2:])
                    settings = id_0_c_components_rgb.get(color_index)

                    if not settings:
                        self.report({'WARNING'}, f"No settings found for material '{material.name}'")
                        continue

                    # Ensure the material uses nodes
                    material.use_nodes = True

                    # Clear existing nodes
                    node_tree = material.node_tree
                    nodes = node_tree.nodes
                    links = node_tree.links
                    nodes.clear()

                    # Create material output node and Super FX node
                    output_node = nodes.new(type="ShaderNodeOutputMaterial")
                    output_node.location = (300, 0)

                    super_fx = nodes.new(type="ShaderNodeGroup")
                    super_fx.node_tree = bpy.data.node_groups["Super FX"]
                    super_fx.location = (0, 0)

                    # Link Super FX to material output
                    links.new(super_fx.outputs["Emission"], output_node.inputs["Surface"])

                    # Assign colors to the Super FX node group inputs
                    for input_name, value in settings.items():
                        if input_name.startswith("Colour"):
                            # Process color inputs
                            if input_name in super_fx.inputs:
                                super_fx.inputs[input_name].default_value = hex_to_rgb(value)
                        else:
                            # Handle other material settings
                            if input_name == "Carry Over":
                                try:
                                    super_fx.inputs[input_name].default_value = float(value)
                                except ValueError:
                                    self.report({'WARNING'}, f"Invalid value for '{input_name}' in material '{material.name}'")

                except ValueError:
                    self.report({'WARNING'}, f"Material '{material.name}' has invalid FX# or FE# format")
                    continue

        self.report({'INFO'}, "Palette applied to materials")
        return {'FINISHED'}


# =========================
# FastFX Menu Panel -  Palette assignment (simple)
# =========================
class OBJECT_OT_apply_material_colors_simple(bpy.types.Operator):
    """Apply colors based on material names (FX#)"""
    bl_idname = "object.apply_material_colors_simple"
    bl_label = "Apply Material Palette (Simple)"

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "No mesh object selected")
            return {'CANCELLED'}

        if not obj.data.materials:
            self.report({'WARNING'}, "No materials found on selected object")
            return {'CANCELLED'}

        for material_slot in obj.material_slots:
            material = material_slot.material
            if material and (material.name.startswith("FX") or material.name.startswith("FE")):
                try:
                    # Extract color index and retrieve the color
                    color_index = int(material.name[2:])
                    hex_color = id_0_c_rgb.get(color_index, "#FFFFFF")  # Default to white

                    # Convert HEX to linear RGB for Blender
                    linear_rgb_color = hex_to_rgb(hex_color)

                    # Ensure the material uses nodes
                    material.use_nodes = True
                    node_tree = material.node_tree

                    # Clear existing nodes
                    nodes = node_tree.nodes
                    links = node_tree.links
                    nodes.clear()

                    # Add a new Principled BSDF node
                    bsdf_node = nodes.new(type="ShaderNodeBsdfPrincipled")
                    bsdf_node.location = (0, 0)

                    # Set the Base Color
                    bsdf_node.inputs["Base Color"].default_value = linear_rgb_color

                    # Add a Material Output node
                    output_node = nodes.new(type="ShaderNodeOutputMaterial")
                    output_node.location = (300, 0)

                    # Connect the BSDF to the Surface input of the Material Output
                    links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

                except ValueError:
                    self.report({'WARNING'}, f"Material '{material.name}' has invalid FX# or FE# format")
                    continue

        self.report({'INFO'}, "Palette applied to materials")
        return {'FINISHED'}


# =========================
# FastFX Menu Panel Layout
# =========================
class VIEW3D_PT_fastfx_tools(bpy.types.Panel):
    """Tools for 3DG1 format"""
    bl_label = "FastFX"
    bl_idname = "VIEW3D_PT_fastfx_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FastFX"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Color Palette (Fancy)")
        layout.operator("object.create_super_fx")
        layout.operator("object.apply_material_colors")
        layout.label(text="Color Palette (Simple)")
        layout.operator("object.apply_material_colors_simple")
        layout.label(text="Vertex Operations")
        layout.operator(VertexOperation.bl_idname, text="Round Vertex Coordinates").operation = 'ROUND'
        layout.operator(VertexOperation.bl_idname, text="Truncate Vertex Coordinates").operation = 'TRUNCATE'
        layout.label(text="Collision Box Tools")
        layout.operator("object.import_colboxes_clipboard")
        layout.operator("object.export_colboxes")
        layout.operator("object.update_colboxes")
        layout.operator("object.update_colbox_offsets")
        layout.operator("object.generate_colbox")


# =========================
# Menu Functions
# =========================
def menu_func_import(self, context):
    self.layout.operator(Import3DG1.bl_idname, text="3DG1/Fundoshi-kun (.txt/.3dg1/.obj)")
    self.layout.operator(ImportBSPOperator.bl_idname, text="Star Fox ASM BSP/GZS (.asm)")
    self.layout.operator(Import3DANOperator.bl_idname, text="3DAN/3DGI/Animated Fundoshi-kun (.anm)")

def menu_func_export(self, context):
    self.layout.operator(Export3DG1.bl_idname, text="3DG1/Fundoshi-kun (.txt/.3dg1/.obj)")
    self.layout.operator(Export3DAN.bl_idname, text="3DAN/3DGI/Animated Fundoshi-kun (.anm)")

# =========================
# Registration
# =========================
def register():
    bpy.utils.register_class(Import3DG1)
    bpy.utils.register_class(Export3DG1)
    bpy.utils.register_class(VertexOperation)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.utils.register_class(OBJECT_OT_apply_material_colors)
    bpy.utils.register_class(OBJECT_OT_apply_material_colors_simple)
    bpy.utils.register_class(VIEW3D_PT_fastfx_tools)
    bpy.utils.register_class(OBJECT_OT_create_super_fx)
    bpy.utils.register_class(OBJECT_OT_import_colboxes_clipboard)
    bpy.utils.register_class(OBJECT_OT_export_colboxes)
    bpy.utils.register_class(OBJECT_OT_update_colboxes)
    bpy.utils.register_class(OBJECT_OT_update_colbox_offsets)
    bpy.utils.register_class(OBJECT_OT_generate_colbox)
    bpy.utils.register_class(ImportBSPOperator)
    bpy.utils.register_class(Import3DANOperator)
    bpy.utils.register_class(Export3DAN)

def unregister():
    bpy.utils.unregister_class(Import3DG1)
    bpy.utils.unregister_class(Export3DG1)
    bpy.utils.unregister_class(VertexOperation)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(OBJECT_OT_apply_material_colors)
    bpy.utils.unregister_class(OBJECT_OT_apply_material_colors_simple)
    bpy.utils.unregister_class(VIEW3D_PT_fastfx_tools)
    bpy.utils.unregister_class(OBJECT_OT_create_super_fx)
    bpy.utils.unregister_class(OBJECT_OT_import_colboxes_clipboard)
    bpy.utils.unregister_class(OBJECT_OT_export_colboxes)
    bpy.utils.unregister_class(OBJECT_OT_update_colboxes)
    bpy.utils.unregister_class(OBJECT_OT_update_colbox_offsets)
    bpy.utils.unregister_class(OBJECT_OT_generate_colbox)
    bpy.utils.unregister_class(ImportBSPOperator)
    bpy.utils.unregister_class(Import3DANOperator)
    bpy.utils.unregister_class(Export3DAN)

if __name__ == "__main__":
    register()
