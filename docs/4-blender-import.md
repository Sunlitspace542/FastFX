[Return to User's Manual index](MANUAL.md)
# 4. Importing Shapes Into Blender
Currently, this addon supports importing the following formats:
- 3DG1/3DGI/3DAN
    - Fundoshi-kun - point coordinates are integers  
    - Model to FX - point coordinates are floats, has extra spacing in between lines in the face list  
    - Blender 2.4 - point coordinates are floats, uses BGR format hex colors for face colors, provided for backwards compatibility with old files.  
- Star Fox ASM BSP format - static and animated
- Star Fox ASM GZS format (BSP format variant) - static and animated
- 3ddraw/Iwamoto 3D-CAD `.cad` and `.nca` files

Go to ``File -> Import -> 3DG1/3DGI/3DAN/Fundoshi-kun`` to import a static or animated model. A `3DGI` file is detected as static when one single-number header line follows its magic, or animated when two do.
Go to ``File -> Import -> Star Fox ASM BSP/GZS (.asm/.bsp)`` to import a Star Fox ASM BSP/GZS format shape.  
Go to ``File -> Import -> Iwamoto CAD/NCA`` to import a CAD model or NCA animation.
The mesh (or meshes if it's an animated shape) should appear. The simple material palette will be applied automatically.  
