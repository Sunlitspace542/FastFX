# FastFX
This Blender addon allows one to Import/Export shapes and collision box data for use with Star Fox 1/2/EX.  
**Blender 3.x is required.** Later Blender versions *might* work to some degree, YMMV.  

# Credits
- Euclidium98 - Super FX material, creating Model to FX, which influenced the design of this addon  
- CoolK - `id_0_c` palette documentation  
- Bisquick - Created [SFView](https://github.com/JDrocks450/StarfoxView), used to generate the simple color palette table
- Kandowontu - Prompting Codex to reverse engineer SHAPED.EXE, creating the codebase that the model compiler library this addon uses is based on

# Features
- 3DG1 format importer/exporter
- ASM BSP (tree or treeless) and GZS export for static and animated shapes through the bundled SHAPED model compiler, plus static and animated BSP/GZS import
- Star Fox 2 slope data tools with built-in or custom slope types and static/animated export
- Custom Super FX material by Euclidium98 to help give a rough idea of what the final product might look like (simple face coloring is also an option, used by default)
- Proper 2-pointed face/edge support (use actual 2-gons or tag stray edges with colors, toggle color/label overlays for edges)
- Faces sorted on export (3DG1 export only)
- Collision box import/export/editing support
- No more `-nan`'s! all point coordinates will be whole integers on export. Any funny calculations should correctly be zeroes now.  

# Supported Formats
## Importing
- 3DG1/3DGI - Fundoshi-kun - point coordinates are integers  
- 3DG1 - Model to FX - point coordinates are floats, has extra spacing in between lines in the face list  
- 3DG1 - Blender 2.4 - point coordinates are floats, uses BGR format hex colors for face colors, provided for backwards compatibility with old files.  
- 3DAN/3DGI - Animated Fundoshi-kun
- Star Fox ASM BSP format - either with a BSP tree or treeless, static and animated
- Star Fox ASM GZS format (BSP format variant) - static and animated

## Exporting
- 3DG1 - Fundoshi-kun  
- 3DAN - Animated Fundoshi-kun
- Star Fox ASM BSP format - with a BSP tree or treeless, static and animated
- Star Fox ASM GZS format (BSP format variant) - static and animated
- Slope data assembler source - static and animated (`.asm` or `.slo`)

# Installation
Run `build_addon.ps1` (Windows PowerShell) / `build.sh` (Linux) to make the addon ZIP, or download a release if one exists. In Blender, go to ``Edit -> Preferences -> Add-ons -> Install...``  
Locate and open ``fastfx.zip``. an addon called FastFX should appear in the window. Click the checkbox to enable it.  

# Usage
For usage instructions, see [the FastFX user's manual](docs/MANUAL.md).

# Disclosure
This addon was made with AI assistance, with direct intervention, fixes, and components provided by me as needed.  
I have thoroughly tested the addon throughout development and all design decisions, concepts, and initial reverse engineering of file formats were provided by me, unless otherwise specified.  
It works well enough for my purposes, at least.  
