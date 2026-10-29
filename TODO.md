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
- [x] faces/edges should be sorted together? sort both separately like before, then together afterward?

## fmt_asm
- [x] allow for importing animations whose jump tables are out of order

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
- [ ] ability to assign multiple shape headers to an object for ASM export? the main label names come from the first
- [ ] convert 2-gons to tagged stray edges? make it toggle for imports (unless animated?) and/or make it a tool in the sidebar, really important that this doesn't screw up the order
- [x] nondestructively merge selected points by distance (allows to merge double sided faces without one side being removed)
- [ ] (ASM) specify that model's points be divided by 2 (use pbd2 macro instead of pb), also make sure asm importer knows how to handle pbd2
- [x] sidebar options which only work in edit mode should all be grayed in other modes
- [x] default filenames for export dialogs (e.g. [object name].[extension])

## OTHER
- [ ] Figure out some way to determine how textures will be mapped on a face beforehand (some way to show which way is "up")?
