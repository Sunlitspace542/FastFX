[Return to User's Manual index](MANUAL.md)
# 3. Animations

Star Fox animations record vertex positions per frame.  
Preprocess the model before animating. Export it as 3DG1 or static ASM and reimport it so vertex order and face sorting are consistent.  
Once animation frames have been created, Only vertex positions can be changed. Any further edits to the mesh will render the animation invalid.

## A. Shape-Key Animation (Default)

With ``Use Legacy Animation Objects`` disabled in the Animation panel, importing an animated 3DAN/3DGI, CAD/NCA, or ASM BSP/GZS file creates one mesh object with a shape key for each frame. The first frame is frame 0. In the Animation panel, use ``Add Frame`` to append a copy of the current frame, ``Insert After`` to copy it directly after the displayed frame, ``Remove Frame`` to delete the displayed frame, the arrow buttons to step between frames, and the outer buttons to jump to the first or last frame. The active shape key is the current frame, so edit its vertex positions in Edit Mode. Frame changes and playback require Object Mode.

``Play/Pause`` plays at up to 20 frames per second. ``Loop Playback`` repeats the animation; ``Mirror Animation`` plays it forward and backward without duplicating the endpoints. The same mirror option is used by animated ASM exports to mirror the jump table without duplicating vertex-frame data. Export menus are unchanged.

For a static 3DG1 or static ASM export of an animated mesh, set ``Static Export Frame`` in the Animation panel to the desired frame number (default 0). Animated 3DAN and ASM exports use all shape-key frames.

## B. Legacy Object-Per-Frame Animation

Enable ``Use Legacy Animation Objects`` in the Animation panel to use the old animation system. Animated imports create one mesh object per frame, and animation exporters use the selected/available frame objects.
For this workflow:

1. Import the preprocessed static model and duplicate per frame, or import an animated file
   while legacy mode is enabled.
2. Name the objects so their frame numbers sort naturally, such as
   `Ship_Frame0`, `Ship_Frame1`, and `Ship_Frame2`.
3. Edit each frame's vertices without changing topology.
4. Select the frame objects and use the existing 3DAN, animated ASM, or
   animated slope-data export menu.

## 3a. Animated Slope Data (Star Fox 2)

Slope assignments can differ between animation frames, but animated slope data must be assigned to the same faces on every frame, and animation and slope polygon toggles must also match. In shape-key mode, change to each frame before assigning its slope data. In legacy mode, assign slope data on each frame object. As with animation, once slope data has been added, the mesh cannot be edited outside of vertex positions or slope assignments, else the slope data will be rendered invalid. Slope animations are exported separately from shapes.  
