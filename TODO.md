# FastFX Rework TODO
Categories are named by their source files.  

## animation
- [ ] allow face sorting options (but NOT point pairing) to apply to animation export? i would make it something the user has to deliberately enable

## colboxes
- N/A

## common
- N/A

## fmt_3dan
- N/A

## fmt_3dg1
- N/A

## fmt_asm
- N/A

## fmt_cad
- N/A

## menus
- N/A
## palette
- [ ] support loading coltabs from source? this would probably need like a ton of work, everything assumes my premade color tables
- [ ] textures??? probably not

## slopes
- N/A

## superfx
- [ ] sidebar controls for aspect X/Y and dither

## ui
- [ ] ability to assign multiple shape headers to an object for ASM export, any fields left blank are inherited from the main one
- [ ] convert 2-gons to tagged stray edges? make it toggle for imports (unless animated?) and/or make it a tool in the sidebar, really important that this doesn't screw up the order
- [ ] (ASM) specify that model's points be divided by 2 (use pbd2 macro instead of pb), also make sure asm importer knows how to handle pbd2

## OTHER
- [ ] Figure out some way to determine how textures will be mapped on a face beforehand (some way to show which way is "up")?
