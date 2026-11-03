# FastFX
# File: textures.py
# Textured material preview tools.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

import bpy
import re


_TEXTURE_UV_MAP = "FastFX Texture UV"
_WIDE_SHEET_SIZE = (256, 128)
_TALL_SHEET_SIZE = (128, 256)


def register_texture_material_settings():
    bpy.types.Material.fastfx_texture_source = bpy.props.EnumProperty(
        name="Texture Source",
        description="Choose an individual texture or a tile from a texture sheet",
        items=[
            ("IMAGE", "Individual Image", "Use a standalone power-of-two texture"),
            ("SHEET", "Texture Sheet", "Extract a texture from an 8x8 tile sheet"),
        ],
        default="IMAGE",
    )
    bpy.types.Material.fastfx_texture_image = bpy.props.PointerProperty(
        name="Image",
        description="Texture image or source sheet",
        type=bpy.types.Image,
    )
    bpy.types.Material.fastfx_texture_sheet_layout = bpy.props.EnumProperty(
        name="Sheet Layout",
        description="Select the physical layout of the texture sheet",
        items=[
            ("WIDE", "Wide (256x128)", "Standard 256x128 sheet"),
            ("TALL", "Tall (128x256)", "Paired 128x32 strips form 256x32 rows"),
        ],
        default="WIDE",
    )
    bpy.types.Material.fastfx_texture_tile_x = bpy.props.IntProperty(
        name="Start Tile X",
        description="Horizontal start position in 8x8 tiles",
        min=0,
        max=31,
        default=0,
    )
    bpy.types.Material.fastfx_texture_tile_y = bpy.props.IntProperty(
        name="Start Tile Y",
        description="Vertical start position in 8x8 tiles, from the top",
        min=0,
        max=15,
        default=0,
    )
    bpy.types.Material.fastfx_texture_tile_width = bpy.props.IntProperty(
        name="Width (Tiles)",
        description="Texture width in 8x8 tiles",
        min=1,
        max=32,
        default=1,
    )
    bpy.types.Material.fastfx_texture_tile_height = bpy.props.IntProperty(
        name="Height (Tiles)",
        description="Texture height in 8x8 tiles",
        min=1,
        max=16,
        default=1,
    )
    bpy.types.Material.fastfx_texture_mirror = bpy.props.BoolProperty(
        name="Mirror Horizontally",
        description="Flip the texture horizontally across the face",
        default=False,
    )


def unregister_texture_material_settings():
    del bpy.types.Material.fastfx_texture_source
    del bpy.types.Material.fastfx_texture_image
    del bpy.types.Material.fastfx_texture_sheet_layout
    del bpy.types.Material.fastfx_texture_tile_x
    del bpy.types.Material.fastfx_texture_tile_y
    del bpy.types.Material.fastfx_texture_tile_width
    del bpy.types.Material.fastfx_texture_tile_height
    del bpy.types.Material.fastfx_texture_mirror


def _texture_index(material):
    name = re.sub(r"\.\d{3}$", "", material.name)
    match = re.fullmatch(r"TX(\d+)", name)
    return int(match.group(1)) if match else None


def is_texture_material(material):
    return material is not None and _texture_index(material) is not None


def _is_power_of_two(value):
    return value > 0 and value & (value - 1) == 0


def _crop_sheet(image, layout, tile_x, tile_y, tile_width, tile_height, name):
    expected_size = _WIDE_SHEET_SIZE if layout == "WIDE" else _TALL_SHEET_SIZE
    if tuple(image.size) != expected_size:
        raise ValueError(
            f"{layout.title()} texture sheets must be {expected_size[0]}x{expected_size[1]} pixels."
        )
    if tile_x < 0 or tile_y < 0 or tile_width <= 0 or tile_height <= 0:
        raise ValueError("Tile positions must be non-negative and tile dimensions must be positive.")
    if tile_x + tile_width > 32 or tile_y + tile_height > 16:
        raise ValueError("The selected tile rectangle extends beyond the logical 256x128 sheet.")

    width = tile_width * 8
    height = tile_height * 8
    source_width, source_height = expected_size
    source_pixels = image.pixels
    pixels = [0.0] * (width * height * 4)

    for destination_y in range(height):
        logical_y = tile_y * 8 + height - 1 - destination_y
        for destination_x in range(width):
            logical_x = tile_x * 8 + destination_x
            if layout == "WIDE":
                source_x = logical_x
                source_y = source_height - 1 - logical_y
            else:
                band = logical_y // 32
                half = logical_x // 128
                source_x = logical_x % 128
                source_y = source_height - 1 - (
                    band * 64 + half * 32 + logical_y % 32
                )

            source_offset = (source_y * source_width + source_x) * 4
            destination_offset = (destination_y * width + destination_x) * 4
            pixels[destination_offset:destination_offset + 4] = source_pixels[
                source_offset:source_offset + 4
            ]

    result = bpy.data.images.new(name, width=width, height=height, alpha=True)
    result.pixels[:] = pixels
    return result


def _texture_preview_metadata(material, source, preview_image):
    source_mode = material.fastfx_texture_source
    metadata = {
        "fastfx_preview_version": 1,
        "fastfx_preview_source_mode": source_mode,
        "fastfx_preview_source_image": source.name,
        "fastfx_preview_source_path": source.filepath,
        "fastfx_preview_image": preview_image.name,
        "fastfx_preview_width_px": int(preview_image.size[0]),
        "fastfx_preview_height_px": int(preview_image.size[1]),
        "fastfx_preview_mirror": bool(material.fastfx_texture_mirror),
        "fastfx_preview_uv_order": "reversed",
    }
    if source_mode == "SHEET":
        metadata.update({
            "fastfx_preview_sheet_layout": material.fastfx_texture_sheet_layout,
            "fastfx_preview_tile_x": int(material.fastfx_texture_tile_x),
            "fastfx_preview_tile_y": int(material.fastfx_texture_tile_y),
            "fastfx_preview_tile_width": int(material.fastfx_texture_tile_width),
            "fastfx_preview_tile_height": int(material.fastfx_texture_tile_height),
        })
    return metadata


def _face_perimeter_uvs(vertex_count):
    """Map face vertices, in mesh order, evenly around the texture perimeter."""
    coordinates = []
    for index in range(vertex_count):
        position = index * 4.0 / vertex_count
        side = int(position)
        fraction = position - side
        if side == 0:
            coordinates.append((fraction, 0.0))
        elif side == 1:
            coordinates.append((1.0, fraction))
        elif side == 2:
            coordinates.append((1.0 - fraction, 1.0))
        else:
            coordinates.append((0.0, 1.0 - fraction))
    return coordinates


def _apply_texture_uvs(obj, material_index, mirror):
    mesh = obj.data
    uv_layer = mesh.uv_layers.get(_TEXTURE_UV_MAP)
    if uv_layer is None:
        uv_layer = mesh.uv_layers.new(name=_TEXTURE_UV_MAP)

    mapped_faces = 0
    unsupported_faces = 0
    for polygon in mesh.polygons:
        if polygon.material_index != material_index:
            continue
        if len(polygon.vertices) < 3:
            unsupported_faces += 1
            continue
        coordinates = list(reversed(_face_perimeter_uvs(len(polygon.loop_indices))))
        for loop_index, (u, v) in zip(polygon.loop_indices, coordinates):
            uv_layer.data[loop_index].uv = (u if mirror else 1.0 - u, v)
        mapped_faces += 1
    mesh.update()
    return mapped_faces, unsupported_faces


def _assign_emissive_texture(material, image):
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (750, 0)
    emission = nodes.new("ShaderNodeEmission")
    emission.location = (250, 100)
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    transparent.location = (250, -150)
    mix_shader = nodes.new("ShaderNodeMixShader")
    mix_shader.location = (500, 0)
    texture = nodes.new("ShaderNodeTexImage")
    texture.location = (0, 0)
    texture.image = image
    texture.interpolation = "Closest"
    texture.extension = "EXTEND"
    uv_map = nodes.new("ShaderNodeUVMap")
    uv_map.location = (-250, 0)
    uv_map.uv_map = _TEXTURE_UV_MAP

    links = material.node_tree.links
    links.new(uv_map.outputs["UV"], texture.inputs["Vector"])
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(texture.outputs["Alpha"], mix_shader.inputs["Fac"])
    links.new(transparent.outputs["BSDF"], mix_shader.inputs[1])
    links.new(emission.outputs["Emission"], mix_shader.inputs[2])
    links.new(mix_shader.outputs["Shader"], output.inputs["Surface"])
    if hasattr(material, "surface_render_method"):
        material.surface_render_method = "DITHERED"
    else:
        material.blend_method = "HASHED"
    material.diffuse_color = (1.0, 1.0, 1.0, 1.0)


class OBJECT_OT_create_texture_material(bpy.types.Operator):
    """Create and assign a TX# textured material"""
    bl_idname = "object.create_texture_material"
    bl_label = "Create TX Material"
    bl_options = {'REGISTER', 'UNDO'}

    texture_index: bpy.props.IntProperty(
        name="Texture Index",
        description="Index used in the TX material name",
        min=0,
        default=0,
    )

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.object.type == "MESH"
            and context.object.mode == "OBJECT"
        )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = context.object
        material_name = f"TX{self.texture_index}"
        material = bpy.data.materials.get(material_name)
        if material is None:
            material = bpy.data.materials.new(name=material_name)

        material_index = next(
            (index for index, slot_material in enumerate(obj.data.materials)
             if slot_material == material),
            None,
        )
        if material_index is None:
            obj.data.materials.append(material)
            material_index = len(obj.data.materials) - 1
        obj.active_material_index = material_index
        self.report({'INFO'}, f"Created or selected {material_name}")
        return {'FINISHED'}


class OBJECT_OT_load_texture_image(bpy.types.Operator):
    """Load a texture image from disk for the active TX# material"""
    bl_idname = "object.load_texture_image"
    bl_label = "Load Texture Image"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(
        default="*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.tga;*.bmp;*.exr;*.hdr",
        options={'HIDDEN'},
    )

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.object.type == "MESH"
            and context.object.mode == "OBJECT"
            and is_texture_material(context.object.active_material)
        )

    def execute(self, context):
        material = context.object.active_material
        try:
            image = bpy.data.images.load(self.filepath, check_existing=True)
        except RuntimeError as error:
            self.report({'ERROR'}, f"Could not load image '{self.filepath}': {error}")
            return {'CANCELLED'}
        material.fastfx_texture_image = image
        material.fastfx_texture_source = "IMAGE"
        self.report({'INFO'}, f"Loaded image '{image.name}'")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class OBJECT_OT_apply_texture_material(bpy.types.Operator):
    """Apply the selected TX# material's emissive texture preview and UVs"""
    bl_idname = "object.apply_texture_material"
    bl_label = "Apply Texture Preview"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.object.type == "MESH"
            and context.object.mode == "OBJECT"
        )

    def execute(self, context):
        obj = context.object
        material = obj.active_material
        if material is None or _texture_index(material) is None:
            self.report({'ERROR'}, "The active material must be named TX followed by a texture index.")
            return {'CANCELLED'}
        material_index = obj.active_material_index
        if (
            material_index < 0
            or material_index >= len(obj.material_slots)
            or obj.material_slots[material_index].material != material
        ):
            self.report({'ERROR'}, "The active material is not assigned to the selected mesh.")
            return {'CANCELLED'}
        assigned_faces = [
            polygon for polygon in obj.data.polygons
            if polygon.material_index == material_index
        ]
        if not any(len(polygon.vertices) >= 3 for polygon in assigned_faces):
            self.report({'WARNING'}, "No faces with three or more vertices use this TX material.")
            return {'CANCELLED'}

        source = material.fastfx_texture_image
        if source is None or source.size[0] <= 0 or source.size[1] <= 0:
            self.report({'ERROR'}, "Choose a loaded texture image or sheet first.")
            return {'CANCELLED'}

        if material.fastfx_texture_source == "IMAGE":
            width, height = source.size
            if not _is_power_of_two(width) or not _is_power_of_two(height):
                self.report({'ERROR'}, "Individual texture width and height must each be powers of two.")
                return {'CANCELLED'}
            preview_image = source
        else:
            width = material.fastfx_texture_tile_width
            height = material.fastfx_texture_tile_height
            try:
                preview_image = _crop_sheet(
                    source,
                    material.fastfx_texture_sheet_layout,
                    material.fastfx_texture_tile_x,
                    material.fastfx_texture_tile_y,
                    width,
                    height,
                    f"{material.name}_TexturePreview",
                )
            except (RuntimeError, ValueError) as error:
                self.report({'ERROR'}, str(error))
                return {'CANCELLED'}

        try:
            if preview_image.packed_file is None:
                preview_image.pack()
        except RuntimeError as error:
            if preview_image != source and preview_image.users == 0:
                bpy.data.images.remove(preview_image)
            self.report({'ERROR'}, f"Could not pack texture image into the blend file: {error}")
            return {'CANCELLED'}

        previous_image_name = material.get("fastfx_texture_preview_image")
        _assign_emissive_texture(material, preview_image)
        if material.fastfx_texture_source == "SHEET":
            material["fastfx_texture_preview_image"] = preview_image.name
        else:
            if "fastfx_texture_preview_image" in material:
                del material["fastfx_texture_preview_image"]
        preview_metadata = _texture_preview_metadata(material, source, preview_image)
        for key, value in preview_metadata.items():
            material[key] = value
            if preview_image != source:
                preview_image[key] = value
        if previous_image_name:
            previous_image = bpy.data.images.get(previous_image_name)
            if (
                previous_image is not None
                and previous_image != source
                and previous_image.users == 0
            ):
                bpy.data.images.remove(previous_image)

        mapped_faces, unsupported_faces = _apply_texture_uvs(
            obj,
            material_index,
            material.fastfx_texture_mirror,
        )
        message = f"Applied texture preview to {mapped_faces} face(s)"
        if unsupported_faces:
            message += f"; skipped {unsupported_faces} face(s) with fewer than three vertices"
        self.report({'INFO'}, message)
        return {'FINISHED'}
