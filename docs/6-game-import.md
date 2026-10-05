[Return to User's Manual index](MANUAL.md)
# 6. Importing into Star Fox
Proper guide coming at some point. For now, the quick summary of this process is:  
- Follow the guide to export the assembly in chapter 3. Either include or copy/paste your BSP/GZS model into one of the master shape files. (located at ``SF\SHAPES\xSHAPESx.ASM`` in UltraStarFox, ``SG\xSHAPESx.ASM`` in vanilla Star Fox, and ``SFES\xSHAPESx.ASM`` in Star Fox EX.)
- Extern the label of your shape (the line above the shape header) in ``SHAPES.EXT``. (located at ``SF\EXT\SHAPES.EXT`` in UltraStarFox, ``SG\SHAPES.EXT`` in vanilla Star Fox, and ``SFES\SHAPES.EXT`` in Star Fox EX.)
- The shape can now be used in game (e.g. maps, strats). Adjust the shape header/colbox scale parameter as needed if your shape is too small.