# FastFX
A Blender plugin for importing/exporting Fundoshi-kun (Modified Videoscape 3DG1) format models for use in Star Fox (2), with additional tools.  
Designed for Blender 3.x, but it might work in 2.8+.  

# Credits
Super FX material: Euclidium98  
Color documentation: CoolK  
Simple color palette data from SFView by Bisquick  

# Installation
Download the ``fastfx.py`` file from this repo. In Blender, go to ``Edit -> Preferences -> Add-ons -> Install...``  
Locate and open ``fastfx.py``. a plugin called FastFX should appear in the window. Click the checkbox to enable it.  

# Usage

## Creating Models
Make a model in Blender. The 3DG1 format can only accept whole numbers for vertex positions, so it is recommended you enable snapping to the nearest increment in Blender.  
Materials must be named in the format ``FX#``, where ``#`` is the color index of that material. See ``Color Reference.png`` for a chart of colors and their IDs.  
Colored edges are also supported. use ``FE#`` instead of ``FX#`` as the material name. That face will be converted to edges when exporting.  
If you are going to make a model composed entirely of edges, you must make a dummy face (a small triangle will work). Assign color 47 to it to make it transparent. If you do not do this, the model will crash the game.  
You can also look at the ``id_0_c_rgb`` dictionary in ``fastfx.py`` itself for color descriptions.  
Use the utility menu to apply the proper color palette (see below).  
  
## Exporting Models
Go to ``File -> Export -> 3DG1/Fundoshi-kun (.txt/.3dg1/.obj)`` to export.  

## Converting to Star Fox BSP Format and Importing into Star Fox
Instructions on how to prepare the model for importing into Star Fox are a WIP.  

## Importing 3DG1 Models
Currently, this plugin only supports importing 2 variants of the 3DG1 format:  
- Fundoshi-kun - point coordinates are integers  
- Model to FX - point coordinates are floats, has extra spacing in between lines in the face list  
  
Go to ``File -> Import -> 3DG1/Fundoshi-kun (.txt/.3dg1/.obj)`` to import.  
The mesh should appear. The color palette will be applied automatically.  

## Utility Menu
FastFX adds a tab on the right hand side of the screen called ``FastFX`` with extra utilities.  
``Create Super FX node group`` creates the node group needed for the Super FX material. You only need to click this once per .blend file.  
``Apply Material Palette (Fancy)`` applies the ``id_0_c`` color palette to all materials following the proper ``FX# / FE#`` naming convention using the Super FX material.  
``Apply Material Palette (Simple)`` applies the ``id_0_c`` color palette to all materials following the proper ``FX# / FE#`` naming convention using simple flat colors.  
``Round Vertex Coordinates`` will round the coordinates of all vertices.  
``Truncate Vertex Coordinates`` will truncate (remove) the fractional portion of all vertex coordinates.  

The 3DG1 exporter will automatically round all vertex coordinates, though you may also want to manually do this.  
In the ``Object`` menu in object mode, there is a new option called ``[FastFX] Vertex Operations``.  

If your model becomes greatly distorted, try scaling it up (preferably by a number divisible by 2), and/or apply scale, then round or truncate.  

# Things this can't do/extra notes
- Sorting faces on export - Star Fox's renderer does not have a Z-buffer. FastFX pre-sorts faces on export based on their distance from the origin. It's pretty good, but there is a chance you may still need to manually sort faces in the 3DG1/BSP afterwards. Remember that whatever comes last in the list is drawn first.  
- Import stray edges with colors - (The 3DG1 importer can read models with colored stray edges, but it's hard to see what material is assigned to a given edge.)  
- Import/Export straight from/to Star Fox BSP format - SHAPED.EXE (Argonaut DOS tool) is still needed to get the 3DG1 into the format Star Fox (2) can actually use.  
- Animation  