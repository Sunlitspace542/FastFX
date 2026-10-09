import bpy
import bmesh
import math
import os
import re

from .fmt_3dan import sort_animation_objects
from .animation import is_vertex_animation

# FastFX
# File: slopes.py
# Functions dealing with slope data creation.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

SLOPE_ENABLED_ATTRIBUTE = "fastfx_slope_enabled"
SLOPE_TYPE_ATTRIBUTE = "fastfx_slope_type"
SLOPE_POLY_ATTRIBUTE = "fastfx_slope_poly"
SLOPE_ANIMATION_ATTRIBUTE = "fastfx_slope_animation"
SLOPE_CUSTOM_TYPES_KEY = "fastfx_slope_custom_types"
_SLOPE_FRAME_ATTRIBUTES = (
    SLOPE_ENABLED_ATTRIBUTE,
    SLOPE_TYPE_ATTRIBUTE,
    SLOPE_POLY_ATTRIBUTE,
    SLOPE_ANIMATION_ATTRIBUTE,
)

SLOPE_TYPES = {
    1: "GROUND",
    2: "WATER",
    3: "ICE",
    4: "GRASS",
}

_SLOPE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def register_slope_settings():
    bpy.types.Scene.fastfx_slope_type = bpy.props.EnumProperty(
        name="Slope Type",
        items=[
            ("GROUND", "Ground", "Standard ground slope"),
            ("WATER", "Water", "Water slope"),
            ("ICE", "Ice", "Ice slope"),
            ("GRASS", "Grass", "Grass slope"),
            ("CUSTOM", "Custom", "Use a custom assembler slope type"),
        ],
        default="GROUND",
    )
    bpy.types.Scene.fastfx_custom_slope_type = bpy.props.StringProperty(
        name="Custom Type",
        description="Custom assembler slope type name",
        default="",
    )
    bpy.types.Scene.fastfx_slope_poly = bpy.props.BoolProperty(
        name="Export Slope Polygon",
        description="Include the SLOPEPOLY outline for assigned faces",
        default=True,
    )
    bpy.types.Scene.fastfx_slope_animation = bpy.props.BoolProperty(
        name="Animate Slope Data",
        description="Export this face's slope data for every selected animation frame",
        default=True,
    )
    bpy.types.Scene.fastfx_show_slope_labels = bpy.props.BoolProperty(
        name="Show Slope Labels",
        description="Show assigned slope types over faces in the 3D Viewport",
        default=True,
    )


def unregister_slope_settings():
    del bpy.types.Scene.fastfx_slope_type
    del bpy.types.Scene.fastfx_custom_slope_type
    del bpy.types.Scene.fastfx_slope_poly
    del bpy.types.Scene.fastfx_slope_animation
    del bpy.types.Scene.fastfx_show_slope_labels


def _animation_slope_attribute_name(attribute_name, frame_index):
    return f"fastfx_anim_slope_{frame_index:04d}_{attribute_name}"


def _read_slope_attribute(mesh, attribute_name):
    attribute = mesh.attributes.get(attribute_name)
    if attribute is None:
        return [0] * len(mesh.polygons)
    if attribute.domain != 'FACE' or attribute.data_type != 'INT':
        raise ValueError(f"Mesh '{mesh.name}' has invalid slope attribute '{attribute_name}'")
    return [item.value for item in attribute.data]


def _write_slope_attribute(mesh, attribute_name, values):
    attribute = mesh.attributes.get(attribute_name)
    if attribute is None:
        attribute = mesh.attributes.new(
            name=attribute_name,
            type='INT',
            domain='FACE',
        )
    if attribute.domain != 'FACE' or attribute.data_type != 'INT':
        raise ValueError(f"Mesh '{mesh.name}' has invalid slope attribute '{attribute_name}'")
    if len(attribute.data) != len(values):
        raise ValueError(f"Mesh '{mesh.name}' changed topology during animation.")
    for item, value in zip(attribute.data, values):
        item.value = value


def initialize_animation_slope_frames(obj, frame_count):
    mesh = obj.data
    active_values = {
        name: _read_slope_attribute(mesh, name)
        for name in _SLOPE_FRAME_ATTRIBUTES
    }
    for frame_index in range(frame_count):
        for name, values in active_values.items():
            _write_slope_attribute(
                mesh,
                _animation_slope_attribute_name(name, frame_index),
                values,
            )
    for name, values in active_values.items():
        _write_slope_attribute(mesh, name, values)


def store_animation_slope_frame(obj, frame_index, bm=None):
    mesh = obj.data
    frame_count = len([
        key for key in mesh.shape_keys.key_blocks
        if key.name.startswith("FastFX_Frame_")
    ])
    if not 0 <= frame_index < frame_count:
        raise ValueError(f"Frame index {frame_index} is outside the animation on '{obj.name}'.")
    if bm is not None:
        for name in _SLOPE_FRAME_ATTRIBUTES:
            source_layer = bm.faces.layers.int.get(name)
            target_name = _animation_slope_attribute_name(name, frame_index)
            target_layer = bm.faces.layers.int.get(target_name)
            if target_layer is None:
                target_layer = bm.faces.layers.int.new(target_name)
            for face in bm.faces:
                face[target_layer] = face[source_layer] if source_layer is not None else 0
        return

    for name in _SLOPE_FRAME_ATTRIBUTES:
        _write_slope_attribute(
            mesh,
            _animation_slope_attribute_name(name, frame_index),
            _read_slope_attribute(mesh, name),
        )


def switch_animation_slope_frame(obj, previous_frame, next_frame):
    mesh = obj.data
    for name in _SLOPE_FRAME_ATTRIBUTES:
        _write_slope_attribute(
            mesh,
            _animation_slope_attribute_name(name, previous_frame),
            _read_slope_attribute(mesh, name),
        )
    for name in _SLOPE_FRAME_ATTRIBUTES:
        _write_slope_attribute(
            mesh,
            name,
            _read_slope_attribute(
                mesh,
                _animation_slope_attribute_name(name, next_frame),
            ),
        )


def add_animation_slope_frame(obj, source_frame):
    mesh = obj.data
    frame_count = len([
        key for key in mesh.shape_keys.key_blocks
        if key.name.startswith("FastFX_Frame_")
    ])
    new_frame = frame_count - 1
    for name in _SLOPE_FRAME_ATTRIBUTES:
        values = _read_slope_attribute(mesh, name)
        _write_slope_attribute(
            mesh,
            _animation_slope_attribute_name(name, source_frame),
            values,
        )
        _write_slope_attribute(
            mesh,
            _animation_slope_attribute_name(name, new_frame),
            values,
        )


def remove_animation_slope_frame(obj, frame_index):
    mesh = obj.data
    frame_count = len([
        key for key in mesh.shape_keys.key_blocks
        if key.name.startswith("FastFX_Frame_")
    ])
    if frame_count <= 1:
        return
    next_frame = min(frame_index, frame_count - 2)
    for name in _SLOPE_FRAME_ATTRIBUTES:
        _write_slope_attribute(
            mesh,
            _animation_slope_attribute_name(name, frame_index),
            _read_slope_attribute(mesh, name),
        )
        for source_index in range(frame_index + 1, frame_count):
            source_name = _animation_slope_attribute_name(name, source_index)
            target_name = _animation_slope_attribute_name(name, source_index - 1)
            _write_slope_attribute(
                mesh,
                target_name,
                _read_slope_attribute(mesh, source_name),
            )
        last_attribute = mesh.attributes.get(
            _animation_slope_attribute_name(name, frame_count - 1)
        )
        if last_attribute is not None:
            mesh.attributes.remove(last_attribute)
        _write_slope_attribute(
            mesh,
            name,
            _read_slope_attribute(
                mesh,
                _animation_slope_attribute_name(name, next_frame),
            ),
        )
    obj["fastfx_animation_frame"] = next_frame


def slope_type_name(mesh, code):
    if code in SLOPE_TYPES:
        return SLOPE_TYPES[code]
    custom_types = list(mesh.get(SLOPE_CUSTOM_TYPES_KEY, []))
    custom_index = code - 5
    if 0 <= custom_index < len(custom_types):
        return custom_types[custom_index]
    raise ValueError(f"Unknown slope type id {code}")


def _display_slope_attribute_names(obj):
    if is_vertex_animation(obj):
        frame_index = obj.fastfx_animation_frame
        return tuple(
            _animation_slope_attribute_name(name, frame_index)
            for name in _SLOPE_FRAME_ATTRIBUTES
        )
    return _SLOPE_FRAME_ATTRIBUTES


def selected_slope_settings(context):
    obj = context.object
    if (
        obj is None
        or obj.type != 'MESH'
        or context.mode != 'EDIT_MESH'
        or obj.mode != 'EDIT'
    ):
        return None

    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    selected_faces = [face for face in bm.faces if face.select]
    active_face = next(
        (
            element
            for element in reversed(tuple(bm.select_history))
            if isinstance(element, bmesh.types.BMFace) and element.select
        ),
        None,
    )
    if active_face is None and selected_faces:
        active_face = selected_faces[-1]

    selection = (
        tuple(face.index for face in selected_faces),
        active_face.index if active_face is not None else None,
    )
    if active_face is None:
        return selection, None

    attribute_names = _display_slope_attribute_names(obj)
    layers = dict(zip(
        _SLOPE_FRAME_ATTRIBUTES,
        (bm.faces.layers.int.get(name) for name in attribute_names),
    ))
    if any(layer is None for layer in layers.values()):
        return selection, None
    if active_face[layers[SLOPE_ENABLED_ATTRIBUTE]] != 1:
        return selection, None

    slope_name = slope_type_name(
        obj.data,
        active_face[layers[SLOPE_TYPE_ATTRIBUTE]],
    )
    return selection, {
        "slope_type": slope_name if slope_name in {"GROUND", "WATER", "ICE", "GRASS"} else "CUSTOM",
        "custom_slope_type": (
            "" if slope_name in {"GROUND", "WATER", "ICE", "GRASS"} else slope_name
        ),
        "slope_poly": bool(active_face[layers[SLOPE_POLY_ATTRIBUTE]]),
        "slope_animation": bool(active_face[layers[SLOPE_ANIMATION_ATTRIBUTE]]),
    }


def slope_face_labels(context, obj):
    labels = []
    if context.mode == 'EDIT_MESH' and obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(obj.data)
        enabled_name, type_name, _, _ = _display_slope_attribute_names(obj)
        enabled_layer = bm.faces.layers.int.get(enabled_name)
        type_layer = bm.faces.layers.int.get(type_name)
        if enabled_layer is None or type_layer is None:
            return labels
        for face in bm.faces:
            if face[enabled_layer] != 1 or len(face.verts) < 3:
                continue
            label = slope_type_name(obj.data, face[type_layer])
            labels.append((face.calc_center_median(), label))
        return labels

    mesh = obj.data
    enabled_name, type_name, _, _ = _display_slope_attribute_names(obj)
    enabled_attribute = mesh.attributes.get(enabled_name)
    type_attribute = mesh.attributes.get(type_name)
    if (
        enabled_attribute is None
        or type_attribute is None
        or enabled_attribute.domain != 'FACE'
        or type_attribute.domain != 'FACE'
        or enabled_attribute.data_type != 'INT'
        or type_attribute.data_type != 'INT'
    ):
        return labels

    for face, enabled, type_value in zip(
        mesh.polygons,
        enabled_attribute.data,
        type_attribute.data,
    ):
        if enabled.value != 1 or len(face.vertices) < 3:
            continue
        labels.append((face.center, slope_type_name(mesh, type_value.value)))
    return labels


class OBJECT_OT_assign_slope_data(bpy.types.Operator):
    """Assign slope settings to selected mesh faces"""
    bl_idname = "object.assign_slope_data"
    bl_label = "Assign Slope Data"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.object.type == 'MESH'
            and context.mode == 'EDIT_MESH'
        )

    def execute(self, context):
        obj = context.object
        scene = context.scene
        bm = bmesh.from_edit_mesh(obj.data)
        selected_faces = [face for face in bm.faces if face.select]
        valid_faces = [face for face in selected_faces if len(face.verts) >= 3]
        if not valid_faces:
            self.report({'WARNING'}, "Select one or more faces with at least three vertices")
            return {'CANCELLED'}

        custom_types = list(obj.data.get(SLOPE_CUSTOM_TYPES_KEY, []))
        if scene.fastfx_slope_type == "CUSTOM":
            slope_name = scene.fastfx_custom_slope_type.strip()
            if not _SLOPE_IDENTIFIER.fullmatch(slope_name):
                self.report(
                    {'ERROR'},
                    "Custom slope type must be an assembler identifier (letters, digits, underscores)",
                )
                return {'CANCELLED'}
            try:
                code = 5 + custom_types.index(slope_name)
            except ValueError:
                custom_types.append(slope_name)
                obj.data[SLOPE_CUSTOM_TYPES_KEY] = custom_types
                code = 4 + len(custom_types)
        else:
            slope_name = scene.fastfx_slope_type
            code = next(key for key, name in SLOPE_TYPES.items() if name == slope_name)

        layer_defaults = (
            (SLOPE_ENABLED_ATTRIBUTE, 0),
            (SLOPE_TYPE_ATTRIBUTE, 1),
            (SLOPE_POLY_ATTRIBUTE, 0),
            (SLOPE_ANIMATION_ATTRIBUTE, 1),
        )
        layers = {}
        for name, default in layer_defaults:
            layer = bm.faces.layers.int.get(name)
            if layer is None:
                layer = bm.faces.layers.int.new(name)
                for face in bm.faces:
                    face[layer] = default
            layers[name] = layer

        for face in valid_faces:
            face[layers[SLOPE_ENABLED_ATTRIBUTE]] = 1
            face[layers[SLOPE_TYPE_ATTRIBUTE]] = code
            face[layers[SLOPE_POLY_ATTRIBUTE]] = int(scene.fastfx_slope_poly)
            face[layers[SLOPE_ANIMATION_ATTRIBUTE]] = int(scene.fastfx_slope_animation)

        if is_vertex_animation(obj):
            store_animation_slope_frame(
                obj,
                obj.fastfx_animation_frame,
                bm=bm,
            )
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        skipped = len(selected_faces) - len(valid_faces)
        message = f"Assigned {slope_name} slope data to {len(valid_faces)} face(s)"
        if skipped:
            message += f"; skipped {skipped} face(s) with fewer than three vertices"
        self.report({'INFO'}, message)
        return {'FINISHED'}


class OBJECT_OT_clear_slope_data(bpy.types.Operator):
    """Clear slope settings from selected mesh faces"""
    bl_idname = "object.clear_slope_data"
    bl_label = "Clear Slope Data"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.object.type == 'MESH'
            and context.mode == 'EDIT_MESH'
        )

    def execute(self, context):
        bm = bmesh.from_edit_mesh(context.object.data)
        layer = bm.faces.layers.int.get(SLOPE_ENABLED_ATTRIBUTE)
        if layer is None:
            self.report({'WARNING'}, "No slope data is assigned to this mesh")
            return {'CANCELLED'}
        selected_faces = [face for face in bm.faces if face.select and face[layer] == 1]
        if not selected_faces:
            self.report({'WARNING'}, "Select faces with slope data to clear")
            return {'CANCELLED'}
        for face in selected_faces:
            face[layer] = 0
        if is_vertex_animation(context.object):
            store_animation_slope_frame(
                context.object,
                context.object.fastfx_animation_frame,
                bm=bm,
            )
        bmesh.update_edit_mesh(context.object.data, loop_triangles=False, destructive=False)
        self.report({'INFO'}, f"Cleared slope data from {len(selected_faces)} face(s)")
        return {'FINISHED'}


def _mesh_slope_records(obj, frame_index=None):
    mesh = obj.data
    from .animation import is_vertex_animation

    if is_vertex_animation(obj) and frame_index is not None:
        attribute_names = tuple(
            _animation_slope_attribute_name(name, frame_index)
            for name in _SLOPE_FRAME_ATTRIBUTES
        )
    else:
        attribute_names = _SLOPE_FRAME_ATTRIBUTES
    attributes = tuple(mesh.attributes.get(name) for name in attribute_names)
    if any(attribute is None for attribute in attributes):
        return []
    if any(attribute.domain != 'FACE' or attribute.data_type != 'INT' for attribute in attributes):
        raise ValueError(f"Mesh '{obj.name}' has invalid slope attributes")

    enabled, types, slope_polys, animations = attributes
    records = []
    for face_index, face in enumerate(mesh.polygons):
        if enabled.data[face_index].value != 1:
            continue
        if len(face.vertices) < 3:
            raise ValueError(f"Face {face_index} on '{obj.name}' has fewer than three vertices")
        slope_name = slope_type_name(mesh, types.data[face_index].value)
        if not _SLOPE_IDENTIFIER.fullmatch(slope_name):
            raise ValueError(f"Face {face_index} has invalid slope type '{slope_name}'")
        records.append((
            face_index,
            tuple(face.vertices),
            slope_name,
            slope_polys.data[face_index].value == 1,
            animations.data[face_index].value == 1,
        ))
    return records


def _slope_coordinates(obj, frame_index=None):
    from .animation import animation_frame_coordinates, is_vertex_animation

    coordinates = (
        animation_frame_coordinates(obj, frame_index)
        if frame_index is not None and is_vertex_animation(obj)
        else [vertex.co for vertex in obj.data.vertices]
    )
    return [
        (
            int(round(-coordinate[0])),
            int(round(-coordinate[2])),
            int(round(-coordinate[1])),
        )
        for coordinate in coordinates
    ]


def _slope_measurements(vertices, face_vertices, face_index):
    points = [vertices[index] for index in face_vertices]
    first, second, third = points[:3]
    edge_a = tuple(second[i] - first[i] for i in range(3))
    edge_b = tuple(third[i] - second[i] for i in range(3))
    normal = (
        edge_a[1] * edge_b[2] - edge_a[2] * edge_b[1],
        edge_a[2] * edge_b[0] - edge_a[0] * edge_b[2],
        edge_a[0] * edge_b[1] - edge_a[1] * edge_b[0],
    )
    normal_length = math.sqrt(sum(value * value for value in normal))
    if normal_length == 0:
        raise ValueError(f"Face {face_index} is degenerate and has no slope plane")
    nx, ny, nz = (value / normal_length for value in normal)
    if abs(ny) < 1e-12:
        raise ValueError(f"Face {face_index} has a vertical slope plane; its center height is undefined")

    center_x = math.trunc(sum(point[0] for point in points) / len(points))
    center_z = math.trunc(sum(point[2] for point in points) / len(points))
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_z = min(point[2] for point in points)
    max_z = max(point[2] for point in points)
    distance = nx * first[0] + ny * first[1] + nz * first[2]
    center_y = math.trunc((nx * center_x + nz * center_z - distance) / ny)
    x_rotation = math.trunc(math.acos(max(-1.0, min(1.0, nz))) * 128 / math.pi - 90)
    z_rotation = math.trunc(math.acos(max(-1.0, min(1.0, nx))) * 128 / math.pi - 90)
    return (
        center_x,
        center_y,
        center_z,
        max_x - min_x,
        max_z - min_z,
        f"{nx * 127:.0f}",
        f"{ny * -127:.0f}",
        f"{nz * 127:.0f}",
        x_rotation,
        z_rotation,
        f"{distance:.0f}",
    )


def _slope_record_line(vertices, face_vertices, slope_name, root_name, poly_name, face_index):
    measurements = _slope_measurements(vertices, face_vertices, face_index)
    fields = [str(value) for value in measurements]
    fields.extend((f"{root_name}_scale", slope_name))
    if poly_name:
        fields.append(poly_name)
    return "\tSLOPE\t" + ",".join(fields)


def _slope_poly_lines(vertices, face_vertices, root_name, slope_ordinal, frame_index):
    poly_name = f"{root_name}_poly{slope_ordinal}_{frame_index}"
    ordered_indices = (face_vertices[0], *reversed(face_vertices))
    lines = [
        f"\n{poly_name}",
        f"\tSLOPEPOLY\t{len(ordered_indices)},{root_name}_scale",
    ]
    for vertex_index in ordered_indices:
        x, _, z = vertices[vertex_index]
        lines.append(f"\tSLOPEPOINT\t{x},{z}")
    return lines


def write_slope_data(filepath, objects, animated=False):
    if not objects or any(obj.type != 'MESH' for obj in objects):
        raise ValueError("Select one or more mesh objects for slope export")
    if any(obj.mode == 'EDIT' for obj in objects):
        raise ValueError("Switch selected meshes to Object Mode before exporting slope data")

    from .animation import animation_frame_count, is_vertex_animation

    shape_key_animation = (
        animated and len(objects) == 1 and is_vertex_animation(objects[0])
    )
    if shape_key_animation:
        frame_objects = [objects[0]] * animation_frame_count(objects[0])
    else:
        frame_objects = sort_animation_objects(objects) if animated else [objects[0]]
    if animated and len(frame_objects) < 2:
        raise ValueError("Select at least two animation frame meshes for animated slope export")
    if animated and objects[0] != frame_objects[0]:
        raise ValueError("Make the first frame mesh active before exporting animated slope data")

    base_mesh = frame_objects[0].data
    topology = tuple(tuple(face.vertices) for face in base_mesh.polygons)
    vertex_count = len(base_mesh.vertices)
    for frame_obj in frame_objects:
        if len(frame_obj.data.vertices) != vertex_count:
            raise ValueError(
                f"Frame '{frame_obj.name}' has {len(frame_obj.data.vertices)} vertices; "
                f"expected {vertex_count}"
            )
        if tuple(tuple(face.vertices) for face in frame_obj.data.polygons) != topology:
            raise ValueError(
                f"Frame '{frame_obj.name}' has different face topology from '{frame_objects[0].name}'"
            )

    if shape_key_animation:
        store_animation_slope_frame(
            frame_objects[0],
            frame_objects[0].fastfx_animation_frame,
        )

    records_by_frame = [
        _mesh_slope_records(
            obj,
            frame_index if shape_key_animation else None,
        )
        for frame_index, obj in enumerate(frame_objects)
    ]
    records = records_by_frame[0]
    if not records:
        raise ValueError(f"No slope data is assigned to '{frame_objects[0].name}'")

    if animated:
        animated_faces_by_frame = [
            {
                face_index
                for face_index, _, _, _, slope_animation in frame_records
                if slope_animation
            }
            for frame_records in records_by_frame
        ]
        animated_faces = animated_faces_by_frame[0]
        for frame_obj, frame_faces in zip(frame_objects[1:], animated_faces_by_frame[1:]):
            if frame_faces != animated_faces:
                raise ValueError(
                    f"Animated slope assignments on '{frame_obj.name}' must match "
                    f"'{frame_objects[0].name}'"
                )

    root_name = os.path.splitext(os.path.basename(filepath))[0]
    if not _SLOPE_IDENTIFIER.fullmatch(root_name):
        raise ValueError("The output filename must start with a letter or underscore and contain only letters, digits, or underscores")

    frame_vertices = [
        _slope_coordinates(obj, frame_index if shape_key_animation else None)
        for frame_index, obj in enumerate(frame_objects)
    ]
    slope_lines = []
    slope_poly_lines = []
    for slope_ordinal, slope_record in enumerate(records):
        face_index, face_vertices, slope_name, slope_poly, slope_animation = slope_record
        if animated and slope_animation:
            frame_records = [
                next(record for record in frame_records if record[0] == face_index)
                for frame_records in records_by_frame
            ]
            if any(record[3] != slope_poly for record in frame_records):
                raise ValueError(
                    f"Animated SLOPEPOLY setting for face {face_index} must match "
                    "across all frames"
                )
            frame_indices = range(len(frame_objects))
        else:
            frame_records = [slope_record]
            frame_indices = range(1)

        if animated and slope_animation:
            slope_lines.append(f"\n\tSLOPEANIM\t{len(frame_objects)}")
        for frame_index, frame_record in zip(frame_indices, frame_records):
            _, frame_face_vertices, frame_slope_name, frame_slope_poly, _ = frame_record
            poly_name = (
                f"{root_name}_poly{slope_ordinal}_{frame_index}"
                if frame_slope_poly else None
            )
            slope_lines.append(_slope_record_line(
                frame_vertices[frame_index],
                frame_face_vertices,
                frame_slope_name,
                root_name,
                poly_name,
                face_index,
            ))
        if slope_poly:
            if animated and slope_animation:
                slope_poly_lines.append(f"\n\tSLOPEANIM\t{len(frame_objects)}")
            for frame_index, frame_record in zip(frame_indices, frame_records):
                _, frame_face_vertices, _, _, _ = frame_record
                slope_poly_lines.extend(_slope_poly_lines(
                    frame_vertices[frame_index],
                    frame_face_vertices,
                    root_name,
                    slope_ordinal,
                    frame_index,
                ))

    with open(filepath, "w", encoding="utf-8", newline="\r\n") as output:
        output.write(";------ Created with FastFX ------\n")
        output.write(f"{root_name}_slo\n")
        output.write(f"\tSLOPES\t{len(records)}\n")
        output.write("\n".join(slope_lines))
        if slope_poly_lines:
            output.write("\n")
            output.write("\n".join(slope_poly_lines))
        output.write("\n")


class ExportSlopeData(bpy.types.Operator):
    """Export assigned slope data as assembler source"""
    bl_idname = "export_mesh.slope_data"
    bl_label = "Export Slope Data"
    bl_options = {'PRESET'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.asm;*.slo", options={'HIDDEN'})
    animated: bpy.props.BoolProperty(
        name="Animated Slope Data",
        description="Export slope data across selected animation frame meshes",
        default=False,
    )

    def execute(self, context):
        if self.animated:
            if (
                not context.scene.fastfx_use_legacy_animation_objects
                and is_vertex_animation(context.active_object)
            ):
                objects = [context.active_object]
            else:
                objects = list(context.selected_objects)
                if context.active_object is None or context.active_object not in objects:
                    self.report({'ERROR'}, "Select all animation frame meshes and make the first frame active")
                    return {'CANCELLED'}
                objects.remove(context.active_object)
                objects.insert(0, context.active_object)
        else:
            obj = context.active_object
            objects = [obj] if obj is not None else []
        try:
            write_slope_data(self.filepath, objects, animated=self.animated)
        except (OSError, ValueError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        kind = "animated " if self.animated else ""
        self.report({'INFO'}, f"Exported {kind}slope data to {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        active = context.active_object
        if active is not None:
            self.filepath = f"{active.name}.slo"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        self.layout.prop(self, "animated")
