[Return to User's Manual index](MANUAL.md)
# 1. FastFX Sidebar
FastFX adds a panel on the right hand side of the screen called ``FastFX`` with extra utilities.  

# Global Configuration

## Game Preset
Configures FastFX to target a specific game.  
- ``Star Fox`` - The standard mode. No slope tools. Simplified ShapeHdr can be enabled if desired, assuming your codebase supports it.
- ``Star Fox 2`` - Slope tools are exposed. In Star Fox 2 mode, the ShapeHdr ``Close LOD Shape`` field is repurposed to point to slope data for the shape. Its label changes to ``Slope Label`` to reflect this. Simplified ShapeHdr cannot be used.
- ``Star Fox EX`` - No slope tools. Simplified ShapeHdr is forced to on as this game requires it.

## Export Options
``Face sorting`` (drop-down):  
- Distance From Origin: sorts faces/edges by their distance from the origin. This is the default setting as it tends to yield decent results.  
- Material Order: sorts faces by the order of the material list in Blender. The last material in the list is drawn first. This is how M2FX handles sorting faces.  
- No Sorting: No sorting operations are performed. Blender's internal hierarchy is used for the face order.  
This setting does not apply to animation exports.  

``Simplified ShapeHdr``: If checked, the ASM shape header is written with LOD parameters omitted. This is meant for compatibility with Star Fox EX.  
This setting is affected by the selected game preset. Star Fox 2 forces it off because the close LOD shape parameter is repurposed as the slope data pointer; Star Fox EX forces it on. The control is disabled for both presets.

``Compress point pairs``: If checked, exact X-mirrored pairs are sorted together at the start of the point list, followed by points that cannot be mirrored. This allows SHAPED to emit one longer `PointsX` block. This setting does not apply to animation exports.  

## Animation
**PLEASE NOTE:** Before animating, export your shape as 3DG1 or static ASM and reimport before animating so the shape is correctly preprocessed for animation.  
``Use Legacy Animation Objects`` - Switches over to the old object-per-frame system used in older versions of FastFX (See chapter 3, section B). All other options in this group apply to the new vertex animation system.
``Static Export Frame`` - Sets which animation frame to use as the basis for static shape exports.
``Start Animation`` - Starts vertex animation.
### Vertex Animation
Displays the current frame number and total with its own set of options.
The main playback controls are: jump to start, previous frame, play/pause, next frame, jump to end.
`Add Frame` Creates a new frame at the end of the animation based on the currently displayed frame.
`Insert After` Inserts a new frame after the currently displayed frame.
`Remove Frame` Removes the displayed frame.
`Loop Playback` Loops animation playback.
`Mirror Animation` Affects both animation playback and ASM export. Animations are played such that the animation is mirrored without repeating any start or end points, e.g. 5 frames of animation would be mirrored as 0,1,2,3,4,3,2,1.
For more information on the animation system, see chapter 3.

# Material Configuration
``Toggle Backface Culling`` toggles backface culling on all materials. This allows for a more accurate representation of the shape in Blender, as Star Fox doesn't draw polygons as double-sided.  


## Color Palette (Simple)
``Apply Material Palette (Simple)`` applies the ``id_0_c`` color palette to all materials following the proper ``FX# / FE#`` naming convention using simple flat colors.  
  


## Color Palette (Fancy)
``PLEASE NOTE``: these features are only known to work on Blender 3.x.  
  
``Create Super FX node group`` creates the node group needed for the Super FX material. You only need to click this once per .blend file.  
  
``Apply Material Palette (Fancy)`` applies the ``id_0_c`` color palette to all materials following the proper ``FX# / FE#`` naming convention using the Super FX material. The node group must exist first.  
  

# Mesh Utilities

The 3DG1 exporter will automatically round all vertex coordinates, though you may also want to manually do this. Options for this are provided in this section.  
The operations available are:  
  
``Round Vertex Coordinates`` will round the coordinates of all vertices.  
  
``Truncate Vertex Coordinates`` will truncate (remove) the fractional portion of all vertex coordinates, e.g. a number such as ``12.34567890`` becomes ``12``.  
  

If your model becomes greatly distorted after using these tools, try scaling it up (preferably by a number divisible by 2), and/or apply scale first, then round or truncate.  

``Add 2-Point Face (OLD)`` adds a 2-point face/2-gon either as a separate object or to the object currently being edited. This is a legacy feature. You should assign materials to plain edges instead.

``Select Twisted Faces`` computes the average face twist for the mesh and selects any quads and N-gons whose vertices twist away from the plane (i.e. their points aren't coplanar). Twisted faces may render unreliably in game. This operator only works in edit mode.  
  
``Merge Points (Keep Faces)`` merges selected points within the specified distance, preserving faces (e.g. in the case of double sided faces). A merge is only prevented if it would result in two corners of the same face being collapsed. This operator only works in edit mode.

``Assign FX Material to Edges`` assigns a selected FX# material in the material pane to a selected plain edge in edit mode.

## Edge Material Overlay
``Show Material Labels`` draws a text overlay over each edge showing the assigned material.
``Show Colored Edge Lines`` draws a colored line overlay on each edge with its assigned material color.

## Slope Data (Star Fox 2)
**PLEASE NOTE:** As with animation, export your shape as 3DG1 or static ASM and reimport before creating slope data so the shape is correctly preprocessed.  
In Edit Mode, select one or more faces with at least three vertices, choose a built-in or custom slope type, configure optional slope polygon (`SLOPEPOLY`) and animation (`SLOPEANIM`) output, and click ``Assign Slope Data``. Click ``Clear Slope Data`` to remove slope assignments from selected faces. Slope types appear as labels drawn over the faces when ``Show Slope Labels`` is enabled.

When faces are selected in Edit Mode, the panel displays the active face's assigned slope type, polygon, and animation settings. With multiple selected faces, the settings for the active (i.e. last selected) face are shown. The controls under ``-Settings to Assign-`` remain the values used when assigning or updating slope data.

In Star Fox 2 mode, use ``File -> Export -> Star Fox 2 Slope Data -> Static Slope Data`` for one mesh. For animation, start an animation, assign slopes on each frame, and use ``Animated Slope Data``. Once animation has been started, the mesh cannot be edited further outside of vertex positions and slope assignments. Both exporters accept ``.slo`` or ``.asm`` extensions.

# Collision Box Tools
``Import Colboxes From Clipboard`` imports colbox definitions from the clipboard.  
  
``Export Colboxes to Clipboard`` copies colbox definitions to the clipboard.  
  
``Export as Animated Colbox`` changes the colbox exporter to allow for exporting animated collision box data. This works similarly to the legacy object-per-frame animation system. Animated colboxes are a series of empties with the name scheme `<prefix>_frameN`, where `N` is a nonzero number.
  
``Update Colboxes From Properties`` updates the empty representing a colbox to match its properties.  
  
``Update Colbox Positions`` updates the position properties of the selected colboxes based on the position of the empties.  
  
``Generate Colbox for Mesh`` generates a colbox that fits the selected mesh. ``NOTE:`` this might cause Blender to crash. Save often and you should be fine.  

# Object Tools
## ASM Tools
``Add ShapeHdr Properties`` assigns all the editable BSP/GZS shape header properties as properties to a selected object. These are used to populate certain fields in the shape header when exporting to assembly.  

### ShapeHdr/Colbox Properties
Click on an object which has ShapeHdr properties added, or a colbox, and its properties will appear in this area.  

ShapeHdr Properties Explanation: 
- Assembly Name - Name to use for the shape's assembler labels. Leave blank to fall back to the export filename. Names can only contain alphanumeric characters and underscores. If the name begins with a number, an underscore will be inserted at the start of the name.
- Z-Sort Priority - Z-sorting priority of the shape when rendered amongst other shapes. Can usually be left as-is. Default is 0.  
- Scale - Scale factor of the shape when rendered in game (equivalent to `1<<n` or `2^n`).  
- Colbox Label - Assembler label pointing to the collision box to use for this shape. 0 falls back to the shape dimensions computed in the header when compiled.  
- Color Palette - Color/texture palette to use for this shape. ``id_0_c`` is used most commonly, is the default, and is the palette FastFX has built in.  
- Shadow Shape - Assembler label of a shape to use for this shape's shadow. if 0, Star Fox's renderer generates a shadow.  
- Close LOD Shape - Assembler label of a shape to use for the close LOD (``simple1``). 0 for none.  
- Mid LOD shape - Assembler label of a shape to use for the mid LOD (``simple2``). 0 for none.  
- Far LOD shape - Assembler label of a shape to use for the far LOD (``simple3``). 0 for none.  

Colbox Properties Explanation:
- Label - Assembler label of this colbox.
- Linked Label - Assembler label of the next colbox in the chain, 0 for none.
- Offset - X/Y/Z offset of the colbox
- Rotation - Set rotation flags. can be `rotx`, `roty`, `rotz`, `rotxyz`, or `norot` for no rotation.
- Dimensions - X/Y/Z dimensions of the colbox.
- Flags Set - Collision flags this colbox will set when hit. Can be `HF1`-`HF8`, or 0 for none.
- Flags Clear - Collision flags this colbox will clear when hit. Can be `HF1`-`HF8`, or 0 for none.
- Scale - Scale factor to apply to the colbox in-game (equivalent to `1<<n` or `2^n`). 

# 1a. Import/Export menus

## File -> Import
- `Fundoshi-kun/Videoscape 3DG1 (.txt/.obj/.anm)` - import a Fundoshi-Kun/Videoscape 3DG1 format shape. Can be either static or animated, the type is detected automatically.
- `Iwamoto CAD/NCA (.cad/.nca)` - import shape files generated by Iwamoto 3D-CAD (3ddraw). `.cad` is static, `.nca` is animated.
- `Star Fox ASM BSP/GZS (.asm/.bsp/.gzs)` - import BSP or GZS format shapes. Can be either static or animated.

## File -> Export
- `Fundoshi-kun/Videoscape 3DG1 (.txt/.obj)` - Export a static Fundoshi-Kun format shape.
- `Animated Fundoshi-kun/3DAN (.anm)`- Export an animated Fundoshi-Kun format shape.
- `Star Fox ASM`- export static ASM shapes. Can be either BSP, treeless BSP, or GZS.
- `Star Fox ASM (Animated)` - export animated ASM shapes. Can be either BSP, treeless BSP, or GZS.
- `Star Fox 2 Slope Data` - this option is only exposed in Star Fox 2 mode. Export either static or animated slope data.