[Return to User's Manual index](MANUAL.md)

# 6. Importing into Star Fox (2)

Proper guide coming at some point. For now, the quick summary of this process is:  

- Follow the guide to export the assembly in chapter 3. Either include or copy/paste your BSP/GZS model into one of the master shape files (e.g. `xSHAPESx.ASM`). 
- Extern the label of your shape (the line above the shape header) in `SHAPES.EXT`.
- The shape can now be used in game (e.g. maps, strats). Adjust the shape header/colbox scale parameter as needed if your shape is too small.

## Shape Source Paths
  
  | Game          | Shapes Path               | Shapes Extern Path   |
  | ------------- | ------------------------- | -------------------- |
  | Star Fox      | `SG\xSHAPESx.ASM`         | `SG\SHAPES.EXT`      |
  | UltraStarFox  | `SF\SHAPES\xSHAPESx.ASM`  | `SF\EXT\SHAPES.EXT`  |
  | Star Fox EX   | `SFES\xSHAPESx.ASM`       | `SFES\SHAPES.EXT`    |
  | Star Fox 2    | `SF2\xSHAPESx.ASM`        | `SF2\SHAPES.EXT`     |
  | UltraStarFox2 | `SF2\SHAPES\xSHAPESx.ASM` | `SF2\EXT\SHAPES.EXT` |
  
  

# 6a. Importing Slope Data (Star Fox 2)
- Export slope data from Blender.
- Insert the output `.SLO` file into `SLOPEDEF.ASM`, and extern the main slope label (the line following the `Created with FastFX` header) in `SLOPEDEF.EXT`.
- Reference the slope data in a shape's header to use the slope data. Slope data is referenced in the same ShapeHdr position as the near LOD shape was in Star Fox. If you created ShapeHdr properties on an object in Blender and the game preset is set to Star Fox 2, this field will be properly labeled.

## Slope Source Paths
  
  | Game          | Slopes Path               | Slopes Extern Path     |
  | ------------- | ------------------------- | ---------------------- |
  | Star Fox 2    | `SF2\SLOPEDEF.ASM`        | `SF2\SLOPEDEF.EXT`     |
  | UltraStarFox2 | `SF2\ASM\SLOPEDEF.ASM`    | `SF2\EXT\SLOPEDEF.EXT` |
  
  