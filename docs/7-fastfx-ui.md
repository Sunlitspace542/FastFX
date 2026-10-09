[Return to User's Manual index](MANUAL.md)
# 7. FastFX Sidebar
FastFX adds a panel on the right hand side of the screen called ``FastFX`` with extra utilities.  

# Global Configuration

## Game Preset
Choose ``Star Fox`` or ``Star Fox 2`` at the top of the sidebar. The default ``Star Fox`` preset hides slope tools, slope labels, and the slope-data export menu. ``Star Fox 2`` exposes these features. In Star Fox 2 mode, the ShapeHdr ``Close LOD Shape`` field is repurposed to point to slope data for the shape. Its label changes to ``Slope Label`` to reflect this.

## Export Options
``Face sorting`` (drop-down):  
- Distance From Origin: sorts faces/edges by their distance from the origin. This is the default setting as it tends to yield decent results.  
- Material Order: sorts faces by the order of the material list in Blender. The last material in the list is drawn first. This is how M2FX handles sorting faces.  
- No Sorting: No sorting operations are performed. Blender's internal hierarchy is used for the face order.  

``Simplified ShapeHdr``: If checked, the shape header is written with LOD parameters omitted. This is meant for compatibility with Star Fox EX.  
This setting is affected by the selected game preset. Star Fox 2 forces it off because a ShapeHdr LOD parameter is repurposed as the slope data pointer; Star Fox EX forces it on. The control is disabled for both presets.

``Compress point pairs``: If checked, exact X-mirrored pairs are sorted together at the start of the point list, followed by points that cannot be mirrored. This allows SHAPED to emit one longer `PointsX` block.

## Vertex Animation
The Animation panel contains the ``Use Legacy Animation Objects`` setting, which selects the old object per frame system. By default, animated imports use one mesh with per-frame shape keys. For a FastFX vertex-animation object, ``Static Export Frame`` selects the zero-based frame used by static 3DG1 and ASM exports.

The panel also shows the current frame and frame count, controls to jump to the first or last frame, step between frames, play/pause, append a copy of the displayed frame, insert a copy immediately after it, and remove the displayed frame. Change frame or edit the frame geometry in Object Mode/Edit Mode respectively; mesh topology must stay fixed. Playback follows the scene frame rate up to a maximum of 20 FPS. It can loop and optionally mirror without duplicating the first or last frame. The mirror option also controls mirrored jump-table output for animated ASM exports. Animated slope data is stored per frame and still exported separately.

# Material Configuration
``Toggle Backface Culling`` toggles backface culling on all materials. This allows for a more accurate representation of the shape in Blender, as Star Fox doesn't draw polygons as double-sided.  

## Color Palette (Fancy)
``PLEASE NOTE``: these features are only known to work on Blender 3.x.  
  
``Create Super FX node group`` creates the node group needed for the Super FX material. You only need to click this once per .blend file.  
  
``Apply Material Palette (Fancy)`` applies the ``id_0_c`` color palette to all materials following the proper ``FX# / FE#`` naming convention using the Super FX material. The node group must exist first.  
  

## Color Palette (Simple)
``Apply Material Palette (Simple)`` applies the ``id_0_c`` color palette to all materials following the proper ``FX# / FE#`` naming convention using simple flat colors.  
  

# Mesh Utilities

The 3DG1 exporter will automatically round all vertex coordinates, though you may also want to manually do this. Options for this are provided in this section.  
The operations available are:  
  
``Round Vertex Coordinates`` will round the coordinates of all vertices.  
  
``Truncate Vertex Coordinates`` will truncate (remove) the fractional portion of all vertex coordinates, e.g. a number such as ``12.34567890`` becomes ``12``.  
  

If your model becomes greatly distorted after using these tools, try scaling it up (preferably by a number divisible by 2), and/or apply scale first, then round or truncate.  

``Add 2-Point Face`` adds a 2-point face/2-gon either as a separate object or to the object currently being edited. This is a legacy feature, It's recommended to assign materials to plain edges instead.

``Select Twisted Faces`` computes the average face twist for the mesh and selects any quads and N-gons whose vertices twist away from the plane. Twisted faces may render unreliably in game. This operator only works in edit mode.  
  

``Assign FX Material to Edges`` assigns a selected FX# material in the material pane to a selected plain edge in edit mode. You may sometimes get an error when attempting to apply materials to loose edges in this way. Just try again and it should eventually go through.  

## Slope Data (Star Fox 2)
In Edit Mode, select one or more faces with at least three vertices, choose a built-in or custom slope type, configure optional ``SLOPEPOLY`` and animation output, and click ``Assign Slope Data``. Click ``Clear Slope Data`` to remove slope assignments from selected faces. Slope types appear as labels over the faces when ``Show Slope Labels`` is enabled.

When faces are selected in Edit Mode, the panel displays the active face's assigned slope type, polygon, and animation settings without changing Blender data during redraw. With multiple selected faces, the active face supplies the displayed settings. The controls under ``Settings to Assign`` remain the values used when assigning or updating slope data.

In the Star Fox 2 preset, use ``File -> Export -> Star Fox 2 Slope Data -> Static Slope Data`` for one mesh. For animation, assign slopes on each frame mesh, select all frames with the first frame active, then use ``Animated Slope Data``. Only matching frame topology can be exported. Both exporters accept ``.slo`` or ``.asm`` filenames.

## Edge Material Overlay
This section allows you to enable/disable the edge color and label overlays if desired.  

# Collision Box Tools
``Import Colboxes From Clipboard`` imports colbox definitions from the clipboard.  
  
``Export Colboxes to Clipboard`` copies colbox definitions to the clipboard.  
  
``Update Colboxes From Properties`` updates the empty representing a colbox to match its properties.  
  
``Update Colbox Positions`` updates the position properties of the selected colboxes based on the position of the empties.  
  
``Generate Colbox for Mesh`` generates a colbox that fits the selected mesh. ``NOTE:`` this can sometimes cause Blender to crash. Save often and you should be fine.  

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