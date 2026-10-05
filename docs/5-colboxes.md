[Return to User's Manual index](MANUAL.md)
# 5. Collision Boxes

## Importing Collision Boxes
Collision boxes have to be in a very specific sanitized format. Remove any extra tabs and manually evaluate any expressions if importing from source.  

The collision box format is as follows:
`[name]	colbox	[linked label], Offset X, Y, Z, rotation flag (rotx/y/z or norot), Dimensions X, Y, Z, flags to set, flags to clear, scale`

For example, properly sanitized and formatted colbox definitions for the player would look like:
```
playerB_col	colbox	playerLW_col,0,0,0,norot,10,10,20,HF1,0,0
playerLW_col	colbox	playerRW_col,-33,13,0,rotz,5,5,10,HF2,0
playerRW_col	colbox	0,33,13,0,rotz,5,5,10,HF3,0
```

## Editing Collision Boxes
```diff  
-CAUTION!-
Blender might crash when using "Generate Colbox for Mesh". Save often.
You have been warned.
```

A colbox's properties can be accessed in the ``Colbox Properties`` section of the FastFX tab in the 3D View sidebar, or in the object's Custom Properties. It is laid out like this:

- Label: Assembler label for the colbox
- Linked label: Assembler label of next colbox to link to this one (if this is the only box or there are no further boxes, enter 0)
- Offset (x, y, z)
- Rotation: rotation allowed for this colbox (can be rotx, roty, rotz, or norot for no rotation)
- Dimensions (x, y, z)
- Flags to clear (can be HF1 - HF8 or 0 for none)
- Flags to set (can be HF1 - HF8 or 0 for none)
- Scale: Shifts dimension and offset fields left by this number when assembled (equivalent to `1<<n` or `2^n`); this is kept for compatibility with the original assembler macro, it is recommended you scale your colboxes properly in Blender so you never have to touch this. Best kept at 0.
  

The easiest way to create a new colbox is to select your mesh and click ``Generate Colbox for Mesh`` to generate a colbox that fits (see above warning about potential crashes when using this).  
  
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