# FastFX Rework TODO
1. BSP tree generation - the BSP algorithm has been cracked thanks to kando throwing SHAPED.EXE at a clanker, this really should be integrated
3. CAD/NCA import - wowjinxy's 3ddraw clone rewrite thing is able to read these, add functionality to import them eventually maybe
2. Animations - Blender supports vertex animation through AnimAll (addon included by default), can we communicate with this for animation import/export?
3. Finally add BSP/GZS animation import/export?
3. Add 2-point face function (I think we need to trick Blender to do this, I created a 3DG1 file with a single 2-point face for this, the idea being we import that 3DG1 and join it to the mesh)
4. Better shape header/colbox setup - this is all a bit fragmented right now and I wish it sucked much less
5. Better side panel in general - Fast64 has a nice side panel, I wish we did
5. (DONE) Split addon code into separate files - it makes testing take a bit longer, but it makes the code less of a hot mess (can we make a build script to simplify testing?)
6. Make point sorting for horizontal mirroring optimization on export optional
7. Button to select twisted faces (shaped has this and I think it'd be useful)
8. Expose sort mode setting in a more obvious place perhaps?
9. Figure out some way to determine how textures will be mapped on a face (some way to show which way is "up")?
10. 2-point faces with materials - is there seriously no way we can render the material on them in the viewport or make it obvious to the user at all??
11. Enforce CRLF line endings on output files - this is to deal with UNIX being UNIX when the files written need to be able to be read by a geriatric assembler stuck on DOS that does not know what LF alone means
12. Slope data import/export for Star Fox 2? Almost no one will use it but it's relevant to have