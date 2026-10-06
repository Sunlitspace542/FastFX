[Return to User's Manual index](MANUAL.md)
# 3. Exporting models

## A. To 3DG1/3DAN

To export to 3DG1, select all frame objects, and go to `File -> Export -> 3DG1/3DGI/Fundoshi-Kun (.txt/.3dg1/.obj)` to export.

If exporting to 3DG1, there will be options on the right hand side of the file picker dialog.  

Face sorting (drop-down):  
- Distance From Origin: sorts faces/edges by their distance from the origin. This is the default setting as it tends to yield decent results.
- Material Order: sorts faces by the order of the material list in Blender. The last material in the list is drawn first. This is how M2FX handles sorting faces.  
- No Sorting: No sorting operations are performed. Blender's internal hierarchy is used for the face order.  

Compress point pairs: Whether the exporter should sort exact X-mirrored pairs together at the start of the point list, followed by points that cannot be mirrored. This allows SHAPED to emit one longer `PointsX` block.

To export to 3DAN, select all frame objects, and go to `File -> Export -> 3DAN/3DGI/Animated Fundoshi-Kun (.anm)` to export. There are no export options in the file picker dialog.

## B. To ASM

## Method 1: Via FastFX
FastFX exports selected static meshes by writing a temporary 3DG1 file and compiling it with the bundled SHAPED model compiler. Coordinates outside the signed 16-bit range (-32768 to 32767) are rejected.

Make a model. Select it in Object Mode and go to the FastFX panel and click ``Add ShapeHdr Properties``. This adds some editable shape header properties to the selected object. Custom ShapeHdr properties are currently not supported in animation export, but will be supported eventually.  
You can edit these properties in the ``ShapeHdr Properties`` section of the FastFX tab in the 3D View sidebar, or in the object's Custom Properties.

Go to ``File -> Export -> Star Fox ASM`` to export.  
Explanation of the 3 supported assembly formats:  
- Star Fox ASM BSP - The most common format. A BSP tree is computed and used to help in Z-sorting.  
- Star Fox ASM BSP (treeless) - The same as BSP, but faces are written as a flat list with no BSP tree information.  
- Star Fox ASM GZS - Similar to treeless BSP, having no BSP tree information, but with a slightly different format and worse Z-sorting.  

Once you select the format, there will be options on the right hand side of the file picker dialog. These options are applied in the 3DG1 export stage.  

Face sorting (drop-down):  
- Distance From Origin: sorts faces/edges by their distance from the origin. This is the default setting as it tends to yield decent results.  
- Material Order: sorts faces by the order of the material list in Blender. The last material in the list is drawn first. This is how M2FX handles sorting faces.  
- No Sorting: No sorting operations are performed. Blender's internal hierarchy is used for the face order.  

Simplified ShapeHdr: If checked, the shape header is written with LOD parameters omitted. This is meant for compatibility with Star Fox EX.  
Compress point pairs: If checked, exact X-mirrored pairs are sorted together at the start of the point list, followed by points that cannot be mirrored. This allows SHAPED to emit one longer `PointsX` block.

For animated ASM export, select all frame mesh objects and use the ``Star Fox ASM (Animated)`` submenu. It gathers all mesh objects in the scene and orders them naturally by **object name**, so name the frames ``Frame0``, ``Frame1``, and so on (``Frame2`` sorts before ``Frame10``).

Each frame must have the same vertex count and face topology; ShapeHdr properties and polygon materials are taken from the first frame in that order.

The SHAPED compiler supports up to 128 frames and 500 points, and coordinates outside the signed 16-bit range (-32768 to 32767) are rejected.

Only the Simplified ShapeHdr option is available when exporting animated assembly shapes. It is expected that you already exported your shape to 3DG1 and reimported before animating so the shape is correctly preprocessed for animation.

## Method 2: WinShaped CLI (the slightly better manual way)
Get WinShaped [here](https://github.com/Sunlitspace542/WinShaped/releases).
Extract it somewhere.

Export your shape as either 3DG1 or 3DAN, then run:
``shaped.exe [format] [input] [output.asm]``
`[format]` can be one of:
```
  --export-gzs input output
  --export-bsp input [output]  (--bsp and -b are aliases)
  --export-pc input output
  --export-internal input output
  --export-3dg1 input output
```
Realistically, you should only use BSP and GZS. See method 1 for an explanation of the two assembly formats.  
The output filename sets the assembler label of the shape in the output assembly.  


## Method 3: DOS SHAPED.EXE (the janky old fashioned way)
Get Shaped [here](https://github.com/Sunlitspace542/FastFX/releases/tag/shaped).  
Extract ``shaped.zip`` somewhere. Run ``run shaped.cmd`` to run Shaped.  

Note that Shaped only supports up to 16 frames of animation (15 if counting from 0). Frame counts greater than that will crash.

To convert:  
1. Export your shape as a 3DG1 (or 3DAN if animated). copy this to Shaped's folder. It is recommended that the filename conform to the MS-DOS 8.3 filename limit. (that being 8 characters for the name, 3 characters for the extension)  
Use the .txt extension for 3DG1 format shapes and the .anm extension for 3DAN format shapes.  
  
2. Run Shaped. Press CTRL+F10 or middle click in the window to capture the mouse.  
  
3. Click on ``Load``. Find your shape file in the dialog that opens, and click OK to load. The wireframe of your shape should appear in the grid.  
  
4. Click on ``Save -> ASM BSP``. Give the output assembly a name by clicking in the ``Name`` box in the dialog that appears and typing in the filename. Press enter to confirm. .ASM is recommended for the extension. Note that the filename you choose also sets the shape's assembler labels to that same name.  
  
5. Press enter again or click OK to convert and save the open shape in BSP format. Close Shaped by clicking on ``Quit -> OK`` or close DOSBOX-X.  
  
6. We need to edit the output a bit for it to be usable in-game. Open the output ASM file and look for a line that looks something like this. If you're using the latest shaped zip, `id_0_c` will already be inserted between the two commas towards the end.  
``	ShapeHdr	MYSHIP_4_P,0,MYSHIP_4_F,0,0,0,0,0,80,36,14,80,80,,0,0,0,0,<MYSHIP_4>``  
This is the shape header.  
Add ``id_0_c`` in between the two commas at the end if not already there (this refers to the color/texture palette), and remove the first number after the 5 zeroes and replace this with a valid colbox label, e.g ``playerB_col``, or ``0`` for no custom colbox.  
Your shape header should now look like this:  
``	ShapeHdr	MYSHIP_4_P,0,MYSHIP_4_F,0,0,0,0,0,playerB_col,36,14,80,80,id_0_c,0,0,0,0,<MYSHIP_4>``
Additionally, if you are going to import the shape into Star Fox EX, you must remove the last 3 parameters before the shape name field in the header. The end result should look like this:  
``	ShapeHdr	MYSHIP_4_P,0,MYSHIP_4_F,0,0,0,0,0,playerB_col,36,14,80,80,id_0_c,0,<MYSHIP_4>``
  
Also scan the file for any instances of `-nan`. these are due to funny math calculations, usually concerning face normals. These should be replaced with zeroes.
  
Save the file.  