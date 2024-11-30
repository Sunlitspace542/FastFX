# FastFX
A Blender plugin for importing/exporting Fundoshi-kun (Modified Videoscape 3DG1) format models for use in Star Fox (2), with additional tools.  
Designed for Blender 3.x, but it might work in 2.8+.  

# Installation
Download the ``fastfx.py`` file from this repo. In Blender, go to ``Edit -> Preferences -> Add-ons -> Install...``  
Locate and open ``fastfx.py``. a plugin called FastFX should appear in the window. Click the checkbox to enable it.  

# Usage

## Creating Models
Make a model in Blender. The 3DG1 format can only accept whole numbers for vertex positions, so it is recommended you enable snapping to the nearest increment in Blender.  
Materials must be named in the format ``FX#``, where ``#`` is the color index of that material. See ``Color Reference.png`` for a chart of colors and their IDs.  
You can also look at the ``id_0_c_rgb`` dictionary in ``fastfx.py`` itself for color descriptions.  
Use the utility menu to apply the proper color palette (see below).  
  
## Exporting Models
Go to ``File -> Export -> 3DG1/Fundoshi-kun (.txt/.3dg1/.obj)`` to export.  

## Converting to Star Fox BSP Format and Importing into Star Fox
Instructions on how to prepare the model for importing into Star Fox are a WIP.  

## Importing 3DG1 Models
NOTE that this only works if the 3DG1 file is in the format that this plugin exports. 3DG1 models in the format Model to FX outputs are currently not supported.  
Go to ``File -> Import -> 3DG1/Fundoshi-kun (.txt/.3dg1/.obj)`` to import.  
The mesh should appear. The color palette will automatically be applied.

## Utility Menu
FastFX adds a tab on the right hand side of the screen called ``FastFX``. with extra utilities.  
``Apply Material Colors`` applies the ``id_0_c`` color palette to all materials following the proper ``FX#`` naming convention.  
``Round Vertex Coordinates`` will round the coordinates of all vertices.  
``Truncate Vertex Coordinates`` will truncate (remove) the fractional portion of all vertex coordinates.  

The 3DG1 exporter will automatically round all vertex coordinates, though you may also want to manually do this.  
In the ``Object`` menu in object mode, there is a new option called ``[FastFX] Vertex Operations``.  

If your model becomes greatly distorted, try scaling it up (preferably by a number divisible by 2), and/or apply scale, then round or truncate.  

# Things this can't do
- Sorting faces on export - Star Fox's renderer does not have a Z-buffer, and while FastFX does appear to do a slightly better job at face sorting compared to Model to FX (a similar tool), it still isn't great.  
- Stray edges (The 3DG1 importer can read models with colored stray edges, but they will not be colored and can only be seen in edit mode. Blender does not let you assign a material to an edge, so exporting stray edges may not work out very well)  
- Import/Export straight from/to Star Fox BSP format - SHAPED.EXE (Argonaut DOS tool) is still needed to get the 3DG1 into the format Star Fox (2) can actually use.  
- Animation  