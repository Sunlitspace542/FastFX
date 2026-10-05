"""Pure-Python implementation of the portable SHAPED model compiler.

The public API intentionally uses plain dataclasses and ``pathlib.Path`` so it
can be embedded in build systems without launching the C executable.
"""

from .core import Dot, FrameDot, Polygon, Shape, ShapeHeader, load, load_colour_tables, write

__all__ = ["Dot", "FrameDot", "Polygon", "Shape", "ShapeHeader", "load", "load_colour_tables", "write"]
