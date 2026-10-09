import bpy


ANIMATION_MARKER = "fastfx_vertex_animation"
ANIMATION_FRAME_PREFIX = "FastFX_Frame_"
ANIMATION_FRAME_PROPERTY = "fastfx_animation_frame"


def is_vertex_animation(obj):
    return (
        obj is not None
        and obj.type == "MESH"
        and bool(obj.get(ANIMATION_MARKER, False))
        and obj.data.shape_keys is not None
    )


def animation_frame_keys(obj):
    if not is_vertex_animation(obj):
        return []
    return [
        key
        for key in obj.data.shape_keys.key_blocks
        if key.name.startswith(ANIMATION_FRAME_PREFIX)
    ]


def animation_frame_count(obj):
    return len(animation_frame_keys(obj))


def animation_frame_coordinates(obj, frame_index):
    keys = animation_frame_keys(obj)
    if not 0 <= frame_index < len(keys):
        raise ValueError(
            f"Frame index {frame_index} is outside the animation on '{obj.name}'."
        )
    return [tuple(vertex.co) for vertex in keys[frame_index].data]


def set_animation_frame(obj, frame_index):
    keys = animation_frame_keys(obj)
    if not keys:
        raise ValueError(f"'{obj.name}' has no FastFX vertex animation.")
    if not 0 <= frame_index < len(keys):
        raise ValueError(
            f"Frame index {frame_index} is outside the animation on '{obj.name}'."
        )
    if obj.mode != "OBJECT":
        raise ValueError("Switch to Object Mode before changing animation frames.")

    if obj.fastfx_animation_frame != frame_index:
        obj.fastfx_animation_frame = frame_index
    else:
        _apply_animation_frame(obj, frame_index)


def create_vertex_animation(obj, frames):
    if obj.type != "MESH":
        raise ValueError("Vertex animation requires a mesh object.")
    if not frames:
        raise ValueError("Vertex animation must contain at least one frame.")
    vertex_count = len(obj.data.vertices)
    if any(len(frame) != vertex_count for frame in frames):
        raise ValueError("Every animation frame must have the same vertex count.")
    if obj.data.shape_keys is not None:
        raise ValueError(f"Mesh '{obj.name}' already has shape keys.")

    basis = obj.shape_key_add(name="Basis", from_mix=False)
    for vertex, coordinate in zip(basis.data, frames[0]):
        vertex.co = coordinate

    for frame_index, coordinates in enumerate(frames):
        key = obj.shape_key_add(
            name=f"{ANIMATION_FRAME_PREFIX}{frame_index:04d}",
            from_mix=False,
        )
        key.relative_key = basis
        for vertex, coordinate in zip(key.data, coordinates):
            vertex.co = coordinate

    obj[ANIMATION_MARKER] = True
    _initialize_slope_frames(obj, len(frames))
    _apply_animation_frame(obj, 0, save_previous=False)
    return obj


def create_animation_object(context, name, frames, polygons):
    if not frames:
        raise ValueError("Cannot create an animated mesh without frames.")
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(frames[0], [], polygons)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    context.collection.objects.link(obj)
    try:
        create_vertex_animation(obj, frames)
    except Exception:
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)
        raise
    return obj


def _update_object_frame(obj, context):
    if not is_vertex_animation(obj):
        return
    count = animation_frame_count(obj)
    if count:
        frame_index = min(max(obj.fastfx_animation_frame, 0), count - 1)
        if frame_index != obj.fastfx_animation_frame:
            obj.fastfx_animation_frame = frame_index
        else:
            _apply_animation_frame(obj, frame_index)


def _apply_animation_frame(obj, frame_index, save_previous=True):
    previous_frame = int(obj.get(ANIMATION_FRAME_PROPERTY, frame_index))
    if save_previous and previous_frame != frame_index:
        _switch_slope_animation_frame(obj, previous_frame, frame_index)
    keys = animation_frame_keys(obj)
    for key_index, key in enumerate(keys):
        key.value = 1.0 if key_index == frame_index else 0.0
    obj.active_shape_key_index = frame_index + 1
    obj[ANIMATION_FRAME_PROPERTY] = frame_index


def register_animation_settings():
    bpy.types.Scene.fastfx_use_legacy_animation_objects = bpy.props.BoolProperty(
        name="Use Legacy Animation Objects",
        description="Import and export animation as separate objects instead of shape keys",
        default=False,
    )
    bpy.types.Scene.fastfx_animation_loop = bpy.props.BoolProperty(
        name="Loop Playback",
        description="Loop playback after the last frame",
        default=True,
    )
    bpy.types.Scene.fastfx_animation_mirror = bpy.props.BoolProperty(
        name="Mirror Animation",
        description="Play frames forward and backward without repeating either endpoint",
        default=False,
    )
    bpy.types.Scene.fastfx_static_export_frame = bpy.props.IntProperty(
        name="Static Export Frame",
        description="Frame of a FastFX vertex animation to use for static exports",
        default=0,
        min=0,
    )
    bpy.types.Object.fastfx_animation_frame = bpy.props.IntProperty(
        name="Current Frame",
        description="Currently displayed FastFX animation frame",
        default=0,
        min=0,
        update=_update_object_frame,
    )
    bpy.types.Scene.fastfx_animation_playing = bpy.props.BoolProperty(
        name="Animation Playing",
        default=False,
        options={'HIDDEN'},
    )


def unregister_animation_settings():
    del bpy.types.Object.fastfx_animation_frame
    del bpy.types.Scene.fastfx_animation_playing
    del bpy.types.Scene.fastfx_static_export_frame
    del bpy.types.Scene.fastfx_animation_mirror
    del bpy.types.Scene.fastfx_animation_loop
    del bpy.types.Scene.fastfx_use_legacy_animation_objects


def _active_animation(context):
    obj = context.active_object
    if not is_vertex_animation(obj):
        raise ValueError("Select an animated mesh object.")
    return obj


class OBJECT_OT_animation_add_frame(bpy.types.Operator):
    """Append a frame copied from the currently displayed geometry"""
    bl_idname = "object.fastfx_animation_add_frame"
    bl_label = "Add Frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            self.report({'ERROR'}, "Select a mesh object.")
            return {'CANCELLED'}
        if obj.mode != "OBJECT":
            self.report({'ERROR'}, "Switch to Object Mode before adding an animation frame.")
            return {'CANCELLED'}
        if context.scene.fastfx_animation_playing:
            self.report({'ERROR'}, "Pause animation playback before changing its frames.")
            return {'CANCELLED'}

        try:
            if is_vertex_animation(obj):
                source_frame = obj.fastfx_animation_frame
                coordinates = animation_frame_coordinates(
                    obj,
                    source_frame,
                )
                key = obj.shape_key_add(
                    name=f"{ANIMATION_FRAME_PREFIX}{animation_frame_count(obj):04d}",
                    from_mix=True,
                )
                key.relative_key = obj.data.shape_keys.key_blocks["Basis"]
                for vertex, coordinate in zip(key.data, coordinates):
                    vertex.co = coordinate
                _add_slope_animation_frame(obj, source_frame)
                set_animation_frame(obj, animation_frame_count(obj) - 1)
            else:
                coordinates = [tuple(vertex.co) for vertex in obj.data.vertices]
                create_vertex_animation(obj, [coordinates, coordinates])
        except (RuntimeError, ValueError, KeyError) as exc:
            self.report({'ERROR'}, f"Could not add animation frame: {exc}")
            return {'CANCELLED'}
        return {'FINISHED'}


class OBJECT_OT_animation_remove_frame(bpy.types.Operator):
    """Remove the currently displayed animation frame"""
    bl_idname = "object.fastfx_animation_remove_frame"
    bl_label = "Remove Frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = _active_animation(context)
            if obj.mode != "OBJECT":
                raise ValueError("Switch to Object Mode before removing an animation frame.")
            if context.scene.fastfx_animation_playing:
                raise ValueError("Pause animation playback before changing its frames.")
            keys = animation_frame_keys(obj)
            if len(keys) <= 1:
                raise ValueError("An animation must retain at least one frame.")
            frame_index = min(obj.fastfx_animation_frame, len(keys) - 1)
            _remove_slope_animation_frame(obj, frame_index)
            obj.shape_key_remove(keys[frame_index])
            for index, key in enumerate(animation_frame_keys(obj)):
                key.name = f"{ANIMATION_FRAME_PREFIX}{index:04d}"
            remaining = animation_frame_count(obj)
            set_animation_frame(obj, min(frame_index, remaining - 1))
        except (RuntimeError, ValueError, KeyError) as exc:
            self.report({'ERROR'}, f"Could not remove animation frame: {exc}")
            return {'CANCELLED'}
        return {'FINISHED'}


class OBJECT_OT_animation_step_frame(bpy.types.Operator):
    """Move one frame backward or forward"""
    bl_idname = "object.fastfx_animation_step_frame"
    bl_label = "Step Animation Frame"
    bl_options = {'INTERNAL'}

    direction: bpy.props.IntProperty(default=1)

    def execute(self, context):
        try:
            obj = _active_animation(context)
            if obj.mode != "OBJECT":
                raise ValueError("Switch to Object Mode before changing animation frames.")
            count = animation_frame_count(obj)
            current = min(obj.fastfx_animation_frame, count - 1)
            set_animation_frame(obj, (current + self.direction) % count)
        except (ValueError, ZeroDivisionError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


class OBJECT_OT_animation_playback(bpy.types.Operator):
    """Play or pause the active FastFX vertex animation"""
    bl_idname = "object.fastfx_animation_playback"
    bl_label = "Play Animation"

    _timer = None
    _frame_direction = 1

    def invoke(self, context, event):
        try:
            self.obj = _active_animation(context)
            if self.obj.mode != "OBJECT":
                raise ValueError("Switch to Object Mode before playing an animation.")
            if animation_frame_count(self.obj) < 2:
                raise ValueError("Add at least two frames before playing an animation.")
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        if context.scene.fastfx_animation_playing:
            context.scene.fastfx_animation_playing = False
            return {'FINISHED'}
        self._frame_direction = 1
        self._timer = context.window_manager.event_timer_add(
            1.0 / max(context.scene.render.fps, 1),
            window=context.window,
        )
        context.window_manager.modal_handler_add(self)
        context.scene.fastfx_animation_playing = True
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'} or not context.scene.fastfx_animation_playing:
            return self._finish(context)
        if event.type != "TIMER":
            return {'PASS_THROUGH'}

        count = animation_frame_count(self.obj)
        current = self.obj.fastfx_animation_frame
        if context.scene.fastfx_animation_loop and context.scene.fastfx_animation_mirror:
            next_frame = current + self._frame_direction
            if next_frame >= count:
                self._frame_direction = -1
                next_frame = count - 2
            elif next_frame < 0:
                self._frame_direction = 1
                next_frame = 1
            set_animation_frame(self.obj, next_frame)
        elif current + 1 < count:
            set_animation_frame(self.obj, current + 1)
        elif context.scene.fastfx_animation_loop:
            set_animation_frame(self.obj, 0)
        else:
            return self._finish(context)
        return {'PASS_THROUGH'}

    def cancel(self, context):
        self._finish(context)

    def _finish(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        context.scene.fastfx_animation_playing = False
        return {'CANCELLED'}


def _initialize_slope_frames(obj, frame_count):
    from .slopes import initialize_animation_slope_frames

    initialize_animation_slope_frames(obj, frame_count)


def _add_slope_animation_frame(obj, source_frame):
    from .slopes import add_animation_slope_frame

    add_animation_slope_frame(obj, source_frame)


def _remove_slope_animation_frame(obj, frame_index):
    from .slopes import remove_animation_slope_frame

    remove_animation_slope_frame(obj, frame_index)


def _switch_slope_animation_frame(obj, previous_frame, next_frame):
    from .slopes import switch_animation_slope_frame

    switch_animation_slope_frame(obj, previous_frame, next_frame)
