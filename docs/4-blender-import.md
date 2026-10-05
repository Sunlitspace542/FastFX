[Return to User's Manual index](MANUAL.md)
# 3. Importing Shapes Into Blender
Currently, this plugin only supports importing 6 formats:  
- 3DG1/3DGI
    - Fundoshi-kun - point coordinates are integers  
    - Model to FX - point coordinates are floats, has extra spacing in between lines in the face list  
    - Blender 2.4 - point coordinates are floats, uses BGR format hex colors for face colors, provided for backwards compatibility with old files.  
- 3DAN/3DGI - Animated Fundoshi-kun
- Star Fox ASM BSP format - static import only, no animation support  
- Star Fox ASM GZS format (BSP format variant) - static import only, no animation support  
  
Go to ``File -> Import -> 3DG1/3DGI/Fundoshi-kun (.txt/.3dg1/.obj)`` to import a 3DG1 format shape.  
Go to ``File -> Import -> Star Fox ASM BSP/GZS (.asm/.bsp)`` to import a Star Fox ASM BSP/GZS format shape.  
Go to ``File -> Import -> 3DG1/3DGI/Animated Fundoshi-kun (.anm)`` to import a 3DGI/3DAN format shape.  
The mesh (or meshes if it's an animated shape) should appear. The simple material palette will be applied automatically.  
