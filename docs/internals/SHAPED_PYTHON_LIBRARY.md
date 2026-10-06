# Python library guide

`shaped` is a dependency-free Python implementation of the portable SHAPED
model reader and selected assembler exporters. It is meant to be embedded in
tools such as Blender add-ons, asset pipelines, and build scripts; it does not
launch the native executable.

## Installation

From a checkout, install into the Python environment used by your tool:

```sh
python -m pip install .
```

For a Blender add-on, the usual approach is to copy the `python/shaped`
directory into the add-on package and import it relatively. The module has no
third-party dependencies.

```python
from .shaped import load, write
```

The implementation requires Python 3.10 or newer.

## Quick conversion

```python
from shaped import load, write

model = load("assets/ship.3dcg")
write(model, "build/ship.asm", "bsp")
```

The supported input signatures are `3DG1`, `3DCG`, `3DAN`, and `3DA1`.
The supported pure-Python writer formats are:

| `write` format | Output |
| --- | --- |
| `"gzs"` | GZS assembler shape |
| `"bsp"` | BSP assembler shape |
| `"internal"` | 3DCG internal/interchange model |
| `"3dg1"` | 3DG1 model |
| `"twist"` | Polygon twist diagnostic report |

Every text writer uses CRLF (`\r\n`) line endings on every platform. The
reader treats `0x1A` as a DOS end-of-file marker and ignores the marker and any
bytes after it.

The PC assembler writer is currently available only in the native CLI.

## The model object

`load()` returns a `Shape` containing simple dataclasses:

```python
from shaped import Dot, FrameDot, Polygon, Shape

shape = Shape(
    dots=[
        Dot(-50, -50, 0),
        Dot(50, -50, 0),
        Dot(0, 50, 0),
    ],
    polygons=[
        Polygon([0, 1, 2], colour=12, flags=1, type=7),
    ],
)
```

`Dot` contains `x`, `y`, `z`, and optional `selected` state. `Polygon` has an
ordered `index` list, `colour`, `flags`, `type`, and optional `selected` state.
The order of a polygon's indices controls its winding and normal direction.

The original fixed limits still apply:

- At most 500 dots and 500 polygons.
- At most 16 vertices per polygon.
- At most 128 animation frames.

`flags=0` makes a polygon inactive. A nonzero `flags` value is also a bitmask
of the original eight shape groups; group 1 is represented by `flags=1`, group
2 by `flags=2`, and so on.

## Animation

For animated shapes, put an equally sized list of `FrameDot` records in every
frame. `FrameDot.active=0` marks a dot inactive for that frame.

```python
from shaped import Dot, FrameDot, Polygon, Shape, write

shape = Shape(
    dots=[Dot(-10, 0, 0), Dot(10, 0, 0), Dot(0, 10, 0)],
    polygons=[Polygon([0, 1, 2], colour=4)],
    frames=[
        [FrameDot(-10, 0, 0), FrameDot(10, 0, 0), FrameDot(0, 10, 0)],
        [FrameDot(-10, 0, 0), FrameDot(10, 0, 0), FrameDot(0, 64, 0)],
    ],
)
write(shape, "animated.asm", "bsp")
```

The assembler header bounds are calculated over all active frames, not merely
the initial frame. This mirrors the C exporter and ensures that animated
motions are included in `xmax`, `ymax`, `zmax`, and radius.

## Blender round trip

You may construct `Shape` objects directly from Blender mesh data, or retain
an existing exporter by writing a temporary `3DG1` or `3DAN` file and loading
it through this library.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from shaped import load, write

with TemporaryDirectory() as temporary:
    source = Path(temporary) / "mesh.3dg"
    write_blender_mesh_as_3dg1(mesh, source)  # supplied by your add-on
    model = load(source)
    write(model, "//build/mesh.asm", "bsp")
```

Use `3DG1` for static meshes. `3DAN` supports per-vertex animation and is read
as a whitespace-delimited stream, so its dot count and frame count may be on
separate lines. Coordinates undergo the original signed 16-bit DOS wrapping
rule during load, so validate coordinate ranges before exporting from Blender.

## Assembler headers

Configure non-file-name assembler symbols and `ShapeHdr` fields with
`ShapeHeader`:

```python
from shaped import ShapeHeader, load, write

model = load("ship.3dg")
model.header = ShapeHeader(
    name="BLENDER_SHIP",       # assembly symbol; does not change filename
    zsort_priority=0,           # default: 0
    scale="SHIP_SCALE",        # default: 0
    colbox="SHIP_COLBOX",      # default: 0
    colour_table="ship_c",     # default: id_0_c
    shadow="SHIP_SHADOW",      # default: 0
    simple1="SHIP_LOD1",       # default: 0
    simple2="SHIP_LOD2",       # default: 0
    simple3="SHIP_LOD3",       # default: 0
)
write(model, "ship.asm", "bsp")
```

The normal header layout is:

```text
ShapeHdr pointptr,bank,faceptr,0,sortz,0,0,scale,colboxptr,
         xmax,ymax,zmax,radius,coltabptr,shadowptr,simple1ptr,
         simple2ptr,simple3ptr,<Name>
```

Use `simplified=True` to emit the short header that omits all three LOD
pointers:

```python
model.header.simplified = True
write(model, "ship.asm", "bsp")
```

For a single call without mutating the header object, use:

```python
write(model, "ship.asm", "bsp", name="OVERRIDE_NAME", simplified_header=True)
```

## Flat BSP face lists

By default, `"bsp"` computes a BSP order and emits a tree when the model needs
one. Force a plain, ordered face list with no `BSP` or `BSPInit` assembler
instructions by passing `tree=False`:

```python
write(model, "ship.asm", "bsp", tree=False)
```

This retains BSP-format points, header, visibility records, and the `name_f1`
face block, but writes active polygons in their current order. It is useful
when a downstream assembler expects BSP-format shapes but does not use tree
traversal.

## Colour tables and smooth normals

The native CLI reads the first `COLTAB` entry from `COLTABS.DAT`. Apply the
same setting explicitly:

```python
from shaped import load, load_colour_tables, write

model = load("ship.3dg")
load_colour_tables(model, "COLTABS.DAT")
write(model, "ship.asm", "gzs")
```

A negative colour-table value enables the vertex-normal block in GZS and BSP
output. The selected table name becomes the header's `colour_table` pointer.

## Blender assembly name

The FastFX add-on exposes an optional **Assembly Name** field in an object's
ShapeHdr properties. A blank value uses the export filename stem. Both custom
names and filename-derived names are sanitized for assembler symbols: runs of
characters other than an ASCII letter, digit, or underscore become an
underscore, and names beginning with a digit are prefixed with an underscore.
The assembly name does not change the exported filename.

For animated exports, the ShapeHdr properties (including **Assembly Name**) on
the first frame object after the add-on's object-name sort are used; properties
on the remaining frame objects do not affect the export.

## Standalone testing frontend

The small command-line frontend loads a model, prints its summary, and exports
one selected Python-supported format:

```sh
python python/shaped/frontend.py
python python/shaped/frontend.py tests/cube.3dg bsp cube.asm
python python/shaped/frontend.py tests/cube.3dg --summary
```

After installation, its command name is `shaped-frontend`.
