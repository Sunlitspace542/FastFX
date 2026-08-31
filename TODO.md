# FastFX Rework TODO
Categories are named by their source files.  

## colboxes
- N/A

## common
- [x] Make point sorting for horizontal mirroring optimization on export optional, deduplicate point pairing code from bsp/gzs and 3dg1 code and consolidate into a shared function

## fmt_3dan
- [ ] Animations - Blender supports vertex animation through AnimAll (addon included by default), can we communicate with this for animation import/export?

## fmt_3dg1
- N/A

## fmt_asm
- [ ] BSP tree generation - the BSP algorithm has been cracked thanks to kando throwing SHAPED.EXE at a clanker, this really should be integrated
- [x] (DONE?) Enforce CRLF line endings on output files - this is to deal with UNIX being UNIX when the files written need to be able to be read by a geriatric assembler stuck on DOS that does not know what LF alone means
- [ ] Finally add BSP/GZS animation import/export?

## menus
- [ ] maybe group BSP/GZS export buttons under a shared category (aesthetic thing)
## palette
- N/A

## superfx
- N/A

## ui
- [x] Add 2-point face function (I think we need to trick Blender to do this, I created a 3DG1 file with a single 2-point face for this, the idea being we import that 3DG1 and join it to the mesh)
- [ ] Better side panel in general - Fast64 has a nice side panel, I wish we did
- [x] Button to select twisted faces (shaped has this and I think it'd be useful)
- [ ] Better shape header/colbox setup - this is all a bit fragmented right now and I wish it sucked much less
- [ ] possibly move export dialog options to menu bar?

## OTHER
- [x] Split addon code into separate files - it makes testing take a bit longer, but it makes the code less of a hot mess (can we make a build script to simplify testing?)
- [ ] 2-point faces with materials - is there seriously no way we can render the material on them in the viewport or make it obvious to the user at all??
- [ ] Slope data import/export for Star Fox 2? Almost no one will use it but it's relevant to have
- [ ] Figure out some way to determine how textures will be mapped on a face beforehand (some way to show which way is "up")?
- [ ] CAD/NCA import - wowjinxy's 3ddraw clone rewrite thing is able to read these, add functionality to import them eventually maybe
