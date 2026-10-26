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
- N/A

## ui
- [ ] ability to assign multiple shape headers to an object for ASM export? the main label names come from the first
- [ ] convert 2-gons to tagged stray edges? either on import and/or make it a tool
- [x] nondestructively merge selected points by distance (allows to merge double sided faces without one side being removed)
- [ ] (ASM) specify that model's points be divided by 2 (use pbd2 macro instead of pb), also make sure asm importer knows how to handle pbd2

## OTHER
- [ ] Figure out some way to determine how textures will be mapped on a face beforehand (some way to show which way is "up")?
