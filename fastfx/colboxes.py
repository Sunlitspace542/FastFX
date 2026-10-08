import bpy
import math
import re

# FastFX
# File: colboxes.py
# Functions concerning Star Fox collision box creation/import/export.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

# =========================
# Colbox importer operator
# =========================
class OBJECT_OT_import_colboxes_clipboard(bpy.types.Operator):
    """Import Collision Boxes From Clipboard"""
    bl_idname = "object.import_colboxes_clipboard"
    bl_label = "Import Colboxes From Clipboard"

    def execute(self, context):
        try:
            imported_count = import_colboxes_from_clipboard()
        except (ValueError, TypeError, IndexError, RuntimeError) as exc:
            self.report({'ERROR'}, f"Failed to import colboxes: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Imported {imported_count} collision box(es)")
        return {'FINISHED'}

# =========================
# Colbox exporter operator
# =========================
class OBJECT_OT_export_colboxes(bpy.types.Operator):
    """Export Collision Boxes to Clipboard"""
    bl_idname = "object.export_colboxes"
    bl_label = "Export Colboxes to Clipboard"

    def execute(self, context):
        try:
            export_colboxes(context)
        except (ValueError, TypeError, IndexError, RuntimeError) as exc:
            self.report({'ERROR'}, f"Failed to export colboxes: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, "Collision box(es) exported successfully!")
        return {'FINISHED'}


def register_colbox_export_settings():
    bpy.types.Scene.fastfx_export_animated_colbox = bpy.props.BoolProperty(
        name="Export as Animated Colbox",
        description="Treat selected <prefix>_frame1, <prefix>_frame2, ... empties as one animated colbox",
        default=False,
    )


def unregister_colbox_export_settings():
    del bpy.types.Scene.fastfx_export_animated_colbox


# =========================
# Colbox exporter
# =========================
def export_colboxes(context):
    selected_colboxes = [obj for obj in context.selected_objects if obj.type == 'EMPTY']
    if context.scene.fastfx_export_animated_colbox:
        colbox_data = _export_animated_colbox(selected_colboxes)
    else:
        colbox_data = [_format_static_colbox(obj) for obj in selected_colboxes]

    bpy.context.window_manager.clipboard = "\n".join(colbox_data)
    return {'FINISHED'}


def _colbox_definition(obj):
    linked_label = obj.get("colbox_linked_label", "0")
    offset = obj.get("colbox_offset", [0, 0, 0])
    rotation = obj.get("colbox_rotation", "norot")
    dimensions = obj.get("colbox_dimensions", [1, 1, 1])
    flags_set = obj.get("colbox_flags_set", "0")
    flags_clear = obj.get("colbox_flags_clear", "0")
    scale = obj.get("colbox_scale", 1)
    return (
        f"{linked_label},{offset[0]},{offset[1]},{offset[2]},"
        f"{rotation},{dimensions[0]},{dimensions[1]},{dimensions[2]},"
        f"{flags_set},{flags_clear},{scale}"
    )


def _format_static_colbox(obj):
    label = obj.get("colbox_label", obj.name)
    return f"{label}\tcolbox\t{_colbox_definition(obj)}"


def _export_animated_colbox(objects):
    frame_pattern = re.compile(r"^(?P<prefix>.+)_frame(?P<frame>[1-9]\d*)$", re.IGNORECASE)
    frames = {}
    prefix = None
    for obj in objects:
        match = frame_pattern.fullmatch(obj.name)
        if match is None:
            raise ValueError(
                f"Animated colbox object '{obj.name}' must be named <prefix>_frame1, "
                "<prefix>_frame2, and so on."
            )
        object_prefix = match.group("prefix")
        if prefix is None:
            prefix = object_prefix
        elif object_prefix != prefix:
            raise ValueError("All selected animated colboxes must share the same name prefix.")

        frame_number = int(match.group("frame"))
        if frame_number in frames:
            raise ValueError(f"Animated colbox frame {frame_number} is selected more than once.")
        frames[frame_number] = obj

    if prefix is None:
        raise ValueError("Select at least one animated colbox frame to export.")

    expected_frames = list(range(1, len(frames) + 1))
    if sorted(frames) != expected_frames:
        raise ValueError("Animated colbox frame names must be contiguous and start at frame 1.")

    output = [prefix, f"\tcolframes {len(frames)}"]
    output.extend(f"\tcolbox\t{_colbox_definition(frames[index])}" for index in expected_frames)
    return output

# =========================
# Colbox importer
# =========================
def import_colboxes_from_clipboard():
    clipboard_content = bpy.context.window_manager.clipboard
    lines = clipboard_content.splitlines()
    imported_count = 0
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue  # Skip empty lines

        stripped = line.strip()
        if "\t" not in stripped:
            label = stripped
            if index + 1 < len(lines) and re.fullmatch(
                r"colframes\s+\d+", lines[index + 1].strip(), re.IGNORECASE
            ):
                frame_count = int(lines[index + 1].strip().split()[1])
                if frame_count < 1:
                    raise ValueError(f"Animated colbox '{label}' must have at least one frame.")
                index += 2
                frame_index = 1
                while frame_index <= frame_count:
                    while index < len(lines) and not lines[index].strip():
                        index += 1
                    if index >= len(lines):
                        raise ValueError(
                            f"Animated colbox '{label}' declares {frame_count} frames "
                            f"but only has {frame_index - 1} definitions."
                        )
                    data = _parse_animated_colbox_line(lines[index], label, frame_index)
                    _create_colbox(f"{label}_frame{frame_index}", data)
                    imported_count += 1
                    frame_index += 1
                    index += 1
                continue

        parts = line.split("\t")
        if len(parts) != 3 or parts[1].strip() != "colbox":
            raise ValueError(f"Invalid colbox line: {line}")
        _create_colbox(parts[0].strip(), parts[2].split(","))
        imported_count += 1
        index += 1

    return imported_count


def _parse_animated_colbox_line(line, label, frame_index):
    parts = line.strip().split("\t")
    if len(parts) != 2 or parts[0].strip() != "colbox":
        raise ValueError(
            f"Expected colbox definition {frame_index} for animated colbox '{label}'."
        )
    return parts[1].split(",")


def _create_colbox(label, colbox_data):
    if len(colbox_data) < 10:
        raise ValueError(f"Colbox '{label}' has an incomplete definition.")

    linked_label = colbox_data[0]
    offset = list(map(int, colbox_data[1:4]))
    rotation = colbox_data[4]
    dimensions = list(map(int, colbox_data[5:8]))
    flags_set = colbox_data[8]
    flags_clear = colbox_data[9]
    scale = int(colbox_data[10]) if len(colbox_data) > 10 else 0

    offset[0] = -offset[0]
    offset[1] = -offset[1]
    offset[1], offset[2] = offset[2], offset[1]
    dimensions[1], dimensions[2] = dimensions[2], dimensions[1]

    obj = bpy.data.objects.get(label) or bpy.data.objects.new(label, None)
    bpy.context.collection.objects.link(obj)
    obj.empty_display_type = 'CUBE'
    obj.empty_display_size = max(dimensions)
    obj.scale = (
        dimensions[0] / obj.empty_display_size,
        dimensions[1] / obj.empty_display_size,
        dimensions[2] / obj.empty_display_size,
    )
    obj.location = offset

    offset[0] = -offset[0]
    offset[2] = -offset[2]
    offset[1], offset[2] = offset[2], offset[1]
    dimensions[1], dimensions[2] = dimensions[2], dimensions[1]

    obj["colbox_label"] = label
    obj["colbox_linked_label"] = linked_label
    obj["colbox_offset"] = offset
    obj["colbox_rotation"] = rotation
    obj["colbox_dimensions"] = dimensions
    obj["colbox_flags_set"] = flags_set
    obj["colbox_flags_clear"] = flags_clear
    obj["colbox_scale"] = scale

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

    # Adjust offset: invert X/Y and swap Y/Z for Blender
    offset[0] = offset[0] * -1
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

    # Adjust offset: invert X/Y and swap Y/Z for Blender
    offset[0] = offset[0] * -1
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

    # Adjust for Blender's coordinate system: swap Y/Z, invert Y/X
    location[2] = location[2] * -1  # Invert Z (Blender's Z = target's Y)
    location[1], location[2] = location[2], location[1]  # Swap Y and Z
    location[0] = -location[0] # X invert

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
        max_corner[2] - min_corner[2],
        max_corner[1] - min_corner[1],
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
    update_colbox(colbox)

    print(f"Collision box '{colbox_label}' created for mesh '{obj.name}'.")
    return colbox
