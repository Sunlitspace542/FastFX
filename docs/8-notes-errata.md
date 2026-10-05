# 8. Notes and Errata

## Notes
- Sorting faces on export - Star Fox's renderer does not have a Z-buffer, and relies on the face order being precalculated by the face order and BSP tree if one exists. FastFX pre-sorts faces on export based on their distance from the origin by default. It's pretty good, but there is a chance you may still need to manually sort faces in the 3DG1/BSP afterwards. Remember that whatever comes last in the material list and the output file's face list is drawn first.  

## Errata
- If using `Generate Colbox for Mesh`, there is a slight chance that Blender will crash. Save often.
