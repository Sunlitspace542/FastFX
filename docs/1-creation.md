[Return to User's Manual index](MANUAL.md)
# 1. Creating Models
Make a model in Blender. The 3DG1/3DAN and ASM formats can only accept whole numbers for vertex positions, also limited to the 16-bit coordinate range for ASM export, so it is strongly recommended you enable snapping to the nearest increment in Blender.

The UI also provides tools to keep points at proper coordinate positions (see the chapter on the UI).  
  
## Materials
Materials must be named in the format ``FX#``, where ``#`` is the color index of that material. See `extras/` for charts of colors in the standard `id_0_c` palette and their numbers. You can also look at the ``id_0_c_rgb`` dictionary in ``fastfx/palette.py`` itself for color descriptions.

Use the FastFX sidebar to apply the proper color palette to the materials (see the chapter on the UI).

## Edges and 2-pointed faces/2-gons
Real 2-gons and stray edges for colored edges are also supported.

For new 2-point faces, select loose edges in Edit Mode, choose an ``FX#`` material as the active material, and click ``Assign FX Material to Edges`` in the FastFX sidebar. Edges used by faces are skipped.

These colored loose edges export as 2-point faces and are deduplicated with edges converted from existing 2-point faces.

### Legacy 2-gon features
You can also create 2-gons directly using the ``Add 2-Point Face`` option in the FastFX sidebar, though this is a legacy feature, and working with real 2-gons in Blender has its quirks and issues. 2-gons are only used when importing a shape or on older projects from before edge tagging was added.

### Edge material overlay
The active mesh's assigned loose edges and existing 2-point faces with ``FX#`` materials display a palette-colored line and material label over the edge in the 3D Viewport; this is a viewport-only visual aid and does not add geometry or affect exports.

The line and label overlays can be toggled independently in the FastFX sidebar under ``Edge Material Overlay``.

## Face to edge conversion (3DG1 and non-animated export only)
To convert faces on a model into edges, use ``FE#`` instead of ``FX#`` as the material name. Please note that ``FE#`` materials are reserved for this feature only and should not be used otherwise. Faces using that material naming scheme will be converted to edges when exporting.

Generated edges are also deduplicated based on if two edges are at the same position and have the same color.  

# 1a. Creating Slope Data (Star Fox 2)
Before creating slope data, export your completed model as 3DG1 and reimport beforehand so the model is correctly face sorted and preprocessed, similar to the procedure for animation.  
Slope records can be assigned to mesh faces and exported as assembler source for SFCAD slope data. In Edit Mode, select the faces, choose ``GROUND``, ``WATER``, ``ICE``, or ``GRASS`` in the FastFX sidebar, then click ``Assign Slope Data``. Choose ``Custom`` to enter another assembler slope type name. Custom names must be valid assembler identifiers.

Enable ``Export Slope Polygon`` when the face also needs a ``SLOPEPOLY`` outline. For animated slopes, apply slope settings to the corresponding face on every frame mesh; slope types can differ between frames, while the animation and polygon toggles must match. Faces must have at least three vertices and define a non-degenerate slope plane; vertical planes cannot produce the center height required by the reference slope format. Assigned slope types are shown over the faces in the viewport and can be cleared from selected faces with ``Clear Slope Data``.

For a static shape, select the mesh and choose ``File -> Export -> Star Fox 2 Slope Data -> Static Slope Data``. Both ``.slo`` and ``.asm`` output are supported.
