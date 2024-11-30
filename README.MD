# FastFX
A Blender plugin for importing/exporting 3DG1 format models for use in Star Fox (2), with additional tools.  
Designed for Blender 3.x, but it might work in 2.8+.  

# Installation
Download the ``fastfx.py`` file from this repo. In Blender, go to ``Edit -> Preferences -> Add-ons -> Install...``  
Locate and open ``fastfx.py``. a plugin called FastFX should appear in the window. Click the checkbox to enable it.  

# How to use

## Exporting Models
Make a model in Blender. The 3DG1 format can only accept whole numbers for vertex positions, so it is recommended you enable snapping to the nearest increment in Blender.  
Materials must be named in the format ``FX#``, where ``#`` is the color index of that material.  
  
Go to ``File -> Export -> Export 3DG1 (.3dg1)`` to export.  

## Converting to Star Fox BSP Format and Importing
Instructions on how to prepare the model for importing into Star Fox are a WIP.  

## Importing Models
NOTE that this only works if the 3DG1 file is in the format that this plugin exports.  
Go to ``File -> Import -> Import 3DG1 (.3dg1)`` to import.  
The mesh should load. Materials will be assigned, but will not have color. This can be manually adjusted.  

## Vertex Operations Menu
The 3DG1 exporter will automatically round all vertex coordinates, though you may also want to manually do this.  
In the ``Object`` menu in object mode, there is a new option called ``[FastFX] Vertex Operations``.  
``Round Vertex Coordinates`` will round the coordinates of all vertices.  
``Truncate Vertex Coordinates`` will truncate (remove) the fractional portion of all vertex coordinates.  
If your model becomes greatly distorted, try scaling it up (preferably by a number divisible by 2), and/or apply scale, then round or truncate.  

# Things this can't do
- Sorting faces on export - Star Fox's renderer does not have a Z-buffer, and while FastFX does appear to do a slightly better job at face sorting compared to Model to FX (a similar tool), it still isn't great.  
- Stray edges (The 3DG1 importer can read models with colored stray edges, but they will not be colored and can only be seen in edit mode. Blender does not let you assign a material to an edge, so exporting stray edges may not work out very well)  
- Import/Export straight from/to Star Fox BSP format - SHAPED.EXE (Argonaut DOS tool) is still needed to get the 3DG1 into the format Star Fox (2) can actually use.  