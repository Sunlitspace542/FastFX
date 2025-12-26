# FastFX
A Blender plugin to Import/Export Fundoshi-kun (3DG1) format shapes and other model data for Star Fox 1/2/EX.
Designed for Blender 3.x, but everything except the Super FX material might work in 2.8+.  

# Credits
Super FX material: Euclidium98  
Color documentation: CoolK  
Simple color palette data from [SFView](https://github.com/JDrocks450/StarfoxView) by Bisquick  

# Features
- 3DG1 format importer/exporter
- Partial ASM BSP/GZS import/export support - no animations, cannot generate BSP trees for Z-sorting in BSP format shapes
- Custom Super FX material by Euclidium98 to help preview what the final product will look like (simple face coloring is also an option, used by default)
- Proper 2-pointed face/edge support
- Faces sorted on export (3DG1 export only)
- Collision box import/export/editing support
- No more ``-nan``'s! all point coordinates will be whole integers on export. (though if you have to use SHAPED, you are at its mercy)

# Supported Formats
## Importing:
- 3DG1 - Fundoshi-kun - point coordinates are integers  
- 3DG1 - Model to FX - point coordinates are floats, has extra spacing in between lines in the face list  
- 3DG1 - Blender 2.4 - point coordinates are floats, uses BGR format hex colors for face colors  
- 3DAN/3DGI - Animated Fundoshi-kun
- Star Fox ASM BSP format - static import only, no animation support  
- Star Fox ASM GZS format (BSP format variant) - static import only, no animation support  

## Exporting:
- 3DG1 - Fundoshi-kun  
- 3DAN - Animated Fundoshi-kun
- Star Fox ASM BSP format - static export only, no animations or BSP trees for face sorting on more complex shapes  
- Star Fox ASM GZS format (BSP format variant) - static export only, no animations, limited face sorting capability  

# Installation
Download the ``fastfx.py`` file from this repo. In Blender, go to ``Edit -> Preferences -> Add-ons -> Install...``  
Locate and open ``fastfx.py``. a plugin called FastFX should appear in the window. Click the checkbox to enable it.  

# Usage

## Creating Models
Make a model in Blender. The Fundoshi-kun 3DG1 format can only accept whole numbers for vertex positions, so it is strongly recommended you enable snapping to the nearest increment in Blender.  
Materials must be named in the format ``FX#``, where ``#`` is the color index of that material. See ``Color Reference.png`` for a chart of colors and their IDs.  
You can also look at the ``id_0_c_rgb`` dictionary in ``fastfx.py`` itself for color descriptions. Use the utility panel to apply the proper color palette (see Utility Panel section below).  
2-pointed faces (AKA stray edges or colored edges) are also supported. use ``FE#`` instead of ``FX#`` as the material name. Faces using that material naming scheme will be converted to edges when exporting. Generated edges are also deduplicated based on if two edges are at the same position and have the same color. A 3DG1 shape file is also included to allow you to import a generic 2-pointed face to use.  
If you are going to make a model composed entirely of 2-pointed faces and are exporting to 3DG1/3DAN, you must either:  
- A: Make a dummy face (a small triangle will work). Assign color 47 to it to make it transparent.  
- B: Create a dummy viz entry in the BSP/GZS after converting with SHAPED.EXE. a vizi count of 1 and a viz entry of all zeroes, e.g. ``	viz	0,0,0 ;0`` will work.  
If you do not do either of these, the shape will crash the game.  
  
## Exporting 3DG1 Models
Go to ``File -> Export -> 3DG1/Fundoshi-kun (.txt/.3dg1/.obj)`` to export.  
There is a drop-down in the export dialog for selecting which method of face sorting to use.  
Face sorting breakdown:  
- Distance From Origin: sorts faces/edges by their distance from the origin. This is the default setting and is recommended for best results.  
- Material Order: sorts faces by the order of the material list in Blender. This is how M2FX handles sorting faces.  
- No Sorting: No sorting operations are performed. Blender's internal hierarchy is used for the face order.  

## Creating Animations
```diff  
-IMPORTANT!-
SHAPED.EXE (the tool used to convert 3DG1/3DAN to BSP) only supports up to 16 frames of animation (15 if counting from 0).
There is currently no other tool that can convert to this format, so be aware of the limitations.
```
Animations in Star Fox are a lot like stop motion. The format logs the changes in vertices for each frame.  
Here's how to do this:  
First, create a model and export it as 3DG1 so the faces are pre-sorted, as the animation exporter **will not** sort faces.  
Create a new Blender document and import the prior 3DG1. Rename it to ``Frame0`` for the first frame.  
Second, press Shift+D, 0 to reset the position, then ENTER to duplicate it. Rename this one to ``Frame1``. Go into edit mode and reposition the vertices for that frame.  
Third, Duplicate that frame, rename it so it is one greater than the previous, make your changes to the vertices, and repeat until you have all your frames.  

## Exporting Animations
Select all the frame objects in Blender. They should all be in order from Frame 0 to whatever your last frame is. Usually Blender will sort the object list for you.  
Go to ``File -> Export -> 3DAN/3DGI/Animated Fundoshi-kun (.anm)`` to export the animation to a .anm file in 3DAN/3DGI format.  
You may need to correct the order of the animation jump tables in the BSP/GZS after converting with SHAPED.EXE if the animation frame order is incorrect.  

## Converting 3DG1/3DAN to Star Fox BSP Format

## Method 1: Via FastFX
```diff  
-WARNING!-
FastFX currently only supports exporting static models to BSP format without BSP trees.
There is no support yet for exporting animations in this format.
It is recommended you use SHAPED for models that have any faces that would overlap without a proper face order.
For simpler shapes however, FastFX's exporter is perfectly usable.
```

Make a model. Select it in Object Mode and go to the FastFX panel and click ``Add ShapeHdr Properties``. This adds some editable shape header properties to the selected object.  
You can edit these properties by selecting the object and going to the Properties section of the Item panel.
  
Explanation:  
- ``zsort_priority`` - Z-sorting priority of the shape when rendered with other shapes. Can usually be left as-is.  
- ``scale`` - Scale factor of the shape when rendered in game. For example, a scale factor of 1 will scale the shape up by 2^1 (equivalent to ``1 << 1``).  
- ``colbox_label`` - Assembler label pointing to the collision box to use for this shape. 0 for none.  
- ``color_palette`` - Color/texture palette to use for this shape. ``id_0_c`` is used most commonly, and is the palette FastFX has built in.  
- ``shadow_shape`` - Assembler label of a shape to use for this shape's shadow. if 0, Star Fox's renderer generates a shadow.  
- ``close_lod_shape`` - Assembler label of a shape to use for the close LOD (AKA ``simple1``). 0 for none.  
- ``mid_lod_shape`` - Assembler label of a shape to use for the mid LOD (AKA ``simple2``). 0 for none.  
- ``far_lod_shape`` - Assembler label of a shape to use for the far LOD (AKA ``simple3``). 0 for none.  
  
Go to ``File -> Export -> Star Fox ASM BSP (treeless) (.asm/.bsp)`` to export.  
There is a drop-down in the export dialog for selecting which method of face sorting to use.  
Face sorting breakdown:  
- Distance From Origin: sorts faces/edges by their distance from the origin. This is the default setting and is recommended for best results.  
- Material Order: sorts faces by the order of the material list in Blender. This is how M2FX handles sorting faces.  
- No Sorting: No sorting operations are performed. Blender's internal hierarchy is used for the face order.  

<!-- EOL -->

There is also a drop-down in the export dialog regarding use of a simplified shape header that excludes LOD information. This is for compatibility with Star Fox EX.  
If you are not using this plugin with that game, you can leave this option set to 'Off'.  
Save the file.  

## Method 2: SHAPED.EXE
Get Shaped [here](https://github.com/Sunlitspace542/FastFX/releases/tag/shaped).  
Extract ``shaped.zip`` somewhere. Run ``run shaped.cmd`` to run Shaped.
To convert:  
1. Export your shape as a 3DG1 (or 3DAN if animated). copy this to Shaped's folder. It is recommended that the filename conform to the MS-DOS 8.3 filename limit. (that being 8 characters for the name, 3 characters for the extension)  
Use the .txt extension for 3DG1 format shapes and the .anm extension for 3DAN format shapes.  
  
2. Run Shaped. Press CTRL+F10 or middle click in the window to capture the mouse.  
  
3. Click on ``Load``. Find your shape file in the dialog that opens, and click OK to load. The wireframe of your shape should appear in the grid.  
  
4. Click on ``Save -> ASM BSP``. Give the output assembly a name by clicking in the ``Name`` box in the dialog that appears and typing in the filename. Press enter to confirm. .ASM is recommended for the extension.  
  
5. Press enter again or click OK to convert and save the open shape in BSP format. Close Shaped by clicking on ``Quit -> OK`` or close DOSBOX-X.  
  
6. We need to edit the output a bit for it to be usable in-game. Open the output ASM file and look for a line that looks something like this:  
``	ShapeHdr	MYSHIP_4_P,0,MYSHIP_4_F,0,0,0,0,0,80,36,14,80,80,,0,0,0,0,<MYSHIP_4>``  
This is the shape header.  
Add ``id_0_c`` in between the two commas at the end (this refers to the color/texture palette), and remove the first number after the 5 zeroes and replace this with a valid colbox label, e.g ``playerB_col``, or ``0`` for no colbox.  
Your shape header should now look like this:  
``	ShapeHdr	MYSHIP_4_P,0,MYSHIP_4_F,0,0,0,0,0,playerB_col,36,14,80,80,id_0_c,0,0,0,0,<MYSHIP_4>``
Additionally, if you are going to import the shape into Star Fox EX, you must remove the last 3 parameters before the shape name field in the header.  
The end result should look like this:  
``	ShapeHdr	MYSHIP_4_P,0,MYSHIP_4_F,0,0,0,0,0,playerB_col,36,14,80,80,id_0_c,0,<MYSHIP_4>``
Save the file.  
## Importing into Star Fox
Proper guide coming at some point. For now, the quick summary of this process is:  
- Either include or copy/paste your BSP/GZS model into one of the master shape files. (located at ``SF\SHAPES\xSHAPESx.ASM`` in UltraStarFox, ``SG\xSHAPESx.ASM`` in vanilla Star Fox, and ``SFES\xSHAPESx.ASM`` in Star Fox EX.)
- Extern the label of your shape (the line above the shape header) in ``SHAPES.EXT``. (located at ``SF\EXT\SHAPES.EXT`` in UltraStarFox, ``SG\SHAPES.EXT`` in vanilla Star Fox, and ``SFES\SHAPES.EXT`` in Star Fox EX.)
- The shape can now be used in game (e.g. maps, strats). Adjust the shape header scale parameter as needed if your shape is too small.

## Importing Shapes
Currently, this plugin only supports importing 6 formats:  
- 3DG1 - Fundoshi-kun - point coordinates are integers  
- 3DG1 - Model to FX - point coordinates are floats, has extra spacing in between lines in the face list  
- 3DG1 - Blender 2.4 - point coordinates are floats, uses BGR format hex colors for face colors  
- 3DAN/3DGI - Animated Fundoshi-kun
- Star Fox ASM BSP format - static import only, no animation support  
- Star Fox ASM GZS format (BSP format variant) - static import only, no animation support  
  
Go to ``File -> Import -> 3DG1/Fundoshi-kun (.txt/.3dg1/.obj)`` to import a 3DG1 format shape.  
Go to ``File -> Import -> Star Fox ASM BSP/GZS (.asm/.bsp)`` to import a Star Fox ASM BSP format shape.  
Go to ``File -> Import -> 3DG1/3DGI/Animated Fundoshi-kun (.anm)`` to import a 3DGI/3DAN format shape.  
Go to ``Star Fox ASM BSP/GZS (.asm/.bsp/.gzs)`` to import a ASM BSP/GZS format shape.  
The mesh (or meshes if it's an animated shape) should appear. The simple material palette will be applied automatically.  

# Collision Boxes
## Importing
Collision boxes have to be in a very specific sanitized format. Remove any extra tabs and manually evaluate any expressions if importing from source.  
For example, properly sanitized and formatted colbox definitions for the player would look like:
```
playerB_col	colbox	playerLW_col,0,0,0,norot,10,10,20,HF1,0,0
playerLW_col	colbox	playerRW_col,-33,13,0,rotz,5,5,10,HF2,0
playerRW_col	colbox	0,33,13,0,rotz,5,5,10,HF3,0
```

## Editing
```diff  
-CAUTION!-
There is a chance Blender may crash when using "Generate Colbox for Mesh". Save often.
You have been warned.
```

A colbox's properties can be accessed from the item panel -> Properties. It is laid out like this:

- dimensions (x, y, z)
- flags to clear (can be HF1 - HF8 or 0 for none)
- flags to set (can be HF1 - HF8 or 0 for none)
- assembler label for the colbox
- label of next colbox to link to this one (if this is the only box or there are no further boxes, enter 0)
- offset (x, y, z)
- rotation allowed for this colbox (can be rotx, roty, rotz, or norot for no rotation)
- scale - shifts dimension and offset fields left by this number when assembled (e.g. a scale of 1 is equivalent to 2^1 or ``1 << 1``); this is kept for compatibility with the original assembler macro, it is recommended you scale your colboxes properly in Blender so you never have to touch this. Best kept at 0.
  

The easiest way to create a new colbox is to select your mesh and click ``Generate Colbox for Mesh`` to generate a colbox that fits.  
  
For meshes that need more than one colbox (e.g things like arches, rings, etc.) you can add a cube, move it and scale it in edit mode to where you want a collision area on your shape, click ``Generate Colbox for Mesh``, and remove the cube. Modify the empty name/colbox property fields as needed afterwards.  
Make sure to link the boxes together using the linked label field in the properties.  
  
You can also manually edit the properties of a colbox empty and apply them by clicking ``Update Colboxes From Properties`` to update the empty to reflect the property changes. Further, you can reposition a colbox empty in Blender and update the coordinates in the empty's properties by clicking ``Update Colbox Positions``.  

## Exporting
Select the colboxes you wish to export, and click ``Export Colboxes to Clipboard`` in the FastFX panel.  
You can then paste them into ``COLBOXES.ASM`` and make them global labels in ``COLBOXES.EXT``  (located in ``SF\ASM\`` and ``SF\EXT`` in UltraStarFox, ``SFES\`` in Star Fox EX, and ``SG\`` in vanilla Star Fox).  
When exporting multiple linked colboxes, make sure they're in order from first to last when adding them into the source or the assembler may throw an error.  
for example:  
```
pillar_col1	colbox	pillar_col2,0,-138,-13,norot,10,80,10,HF1,0,0
pillar_col2	colbox	0,0,-138,-13,norot,10,80,10,HF1,0,0
```
For a shape to use a colbox you have created, you must reference the first colbox all others (if any) link to in the colbox field of its shape header. e.g. For the above example, ``pillar_col1`` would be referenced in the shape header.  

## Utility Panel
FastFX adds a panel on the right hand side of the screen called ``FastFX`` with extra utilities.  

### Material Configuration:
``Toggle Backface Culling`` toggles backface culling on all materials. This allows for a more accurate representation of the shape in Blender, as Star Fox doesn't draw polygons as double-sided.  

### Color Palette (Fancy):
**PLEASE NOTE**: these features are only known to work on Blender 3.x.  
  
``Create Super FX node group`` creates the node group needed for the Super FX material. You only need to click this once per .blend file.  
  
``Apply Material Palette (Fancy)`` applies the ``id_0_c`` color palette to all materials following the proper ``FX# / FE#`` naming convention using the Super FX material. The node group must exist first.  
  

### Color Palette (Simple):
``Apply Material Palette (Simple)`` applies the ``id_0_c`` color palette to all materials following the proper ``FX# / FE#`` naming convention using simple flat colors.  
  

### Vertex Operations

The 3DG1 exporter will automatically round all vertex coordinates, though you may also want to manually do this.  
The operations available are:  
  
``Round Vertex Coordinates`` will round the coordinates of all vertices.  
  
``Truncate Vertex Coordinates`` will truncate (remove) the fractional portion of all vertex coordinates, e.g. a number such as ``12.34567890`` becomes ``12``.  
  
If your model becomes greatly distorted after using these tools, try scaling it up (preferably by a number divisible by 2), and/or apply scale first, then round or truncate.  

### Collision Box Tools
``Import Colboxes From Clipboard`` imports colbox definitions from the clipboard.  
  
``Export Colboxes to Clipboard`` copies colbox definitions to the clipboard.  
  
``Update Colboxes From Properties`` updates the empty representing a colbox to match its properties.  
  
``Update Colbox Positions`` updates the position properties of the selected colboxes based on the position of the empties.  
  
``Generate Colbox for Mesh`` generates a colbox that fits the selected mesh. **NOTE:** this can sometimes cause Blender to crash. Save often and you should be fine.  

### BSP/GZS Tools
``Add ShapeHdr Properties`` assigns all the editable BSP/GZS shape header properties as properties to a selected object.

# Things this can't do/extra notes
- Sorting faces on export - Star Fox's renderer does not have a Z-buffer. FastFX pre-sorts faces on export based on their distance from the origin by default. It's pretty good, but there is a chance you may still need to manually sort faces in the 3DG1/BSP afterwards. Remember that whatever comes last in the material list and the output face list is drawn first.  
- Import stray edges (2-pointed faces) with colors - FastFX can import and export 2-pointed faces, but the material assigned to them will not be visible in the viewport.  
- Import/Export straight from/to Star Fox BSP format - SHAPED.EXE (Argonaut DOS tool) is still needed to get the 3DG1 into the format Star Fox (2) can actually use. Reverse engineering and documentation of the BSP format is a work in progress. Most of the format has now been cracked, though animations in this format and BSP tree generation/Z-sorting are currently not supported.  