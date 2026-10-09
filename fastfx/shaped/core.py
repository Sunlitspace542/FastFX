"""Model formats and exporters matched to ``src/main.c``.

All writer methods emit CRLF, regardless of the host platform.  Coordinates
use the original signed-16-bit DOS wrapping rule, including on input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, sqrt, trunc
from pathlib import Path
import re
from typing import Iterable, Literal

MAX_DOTS = 500
MAX_POLYS = 500
MAX_POLY_VERTS = 16
MAX_FRAMES = 128


class FormatError(ValueError):
    """The input is not a valid supported SHAPED interchange file."""


def _dos(value: float) -> float:
    if not isfinite(value):
        return 0.0
    value = int(trunc(value)) & 0xFFFF
    return float(value - 0x10000 if value >= 0x8000 else value)


def _number(value: float) -> str:
    return f"{value:.0f}"


def _crlf(path: Path, text: str) -> None:
    path.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))


@dataclass
class Dot:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    selected: bool = False


@dataclass
class FrameDot:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    active: int = 1


@dataclass
class Polygon:
    index: list[int]
    colour: int = 1
    flags: int = 1
    type: int = 7
    selected: bool = False


@dataclass
class _BspNode:
    poly: int
    front: int = -1
    back: int = -1
    leaf: bool = True


@dataclass
class ShapeHeader:
    """Assembler ``ShapeHdr`` fields controlled by an embedding application.

    Values may be assembler labels or ``0``. ``simplified`` omits the three
    optional LOD pointers, matching the short form used by the original tools.
    """

    name: str | None = None
    scale: str | int = 0
    colbox: str | int = 0
    colour_table: str | int = "id_0_c"
    shadow: str | int = 0
    simple1: str | int = 0
    simple2: str | int = 0
    simple3: str | int = 0
    simplified: bool = False
    zsort_priority: str | int = 0


@dataclass
class Shape:
    dots: list[Dot] = field(default_factory=list)
    polygons: list[Polygon] = field(default_factory=list)
    frames: list[list[FrameDot]] = field(default_factory=list)
    source: Path | None = None
    current_frame: int = 0
    smooth_shade: bool = False
    header: ShapeHeader = field(default_factory=ShapeHeader)

    def __post_init__(self) -> None:
        if len(self.dots) > MAX_DOTS or len(self.polygons) > MAX_POLYS:
            raise FormatError("SHAPED capacity exceeded")
        if self.frames and any(len(frame) != len(self.dots) for frame in self.frames):
            raise FormatError("frame dot count differs from shape dot count")

    def dot_at(self, index: int, frame: int | None = None) -> Dot:
        frame = self.current_frame if frame is None else frame
        if self.frames and 0 <= frame < len(self.frames):
            dot = self.frames[frame][index]
            return Dot(dot.x, dot.y, dot.z)
        return self.dots[index]

    def active(self, index: int, frame: int | None = None) -> bool:
        frame = self.current_frame if frame is None else frame
        return not self.frames or frame >= len(self.frames) or self.frames[frame][index].active != 0

    @property
    def frame_count(self) -> int:
        return len(self.frames) or 1

    def save_internal(self, path: str | Path) -> None:
        slots = 0
        for index in range(len(self.dots)):
            if self.active(index):
                slots = index + 1
        lines = ["3DCG", f"{slots} {self.frame_count}"]
        for frame in range(self.frame_count):
            for index in range(slots):
                dot = self.dot_at(index, frame)
                active = self.frames[frame][index].active if self.frames else 1
                lines.append(f"{_number(dot.x)} {_number(dot.y)} {_number(dot.z)},{active}" if active else "0 0 0,0")
        for polygon in self.polygons:
            if not polygon.flags:
                continue
            flags = (polygon.flags & ~0x100) | (0x100 if polygon.selected else 0)
            lines.append(f"{len(polygon.index)} {' '.join(map(str, polygon.index))} ,{polygon.colour} 0x{flags:X} 0x{polygon.type:X}")
        _crlf(Path(path), "\n".join(lines) + "\n")

    def save_3dg1(self, path: str | Path) -> None:
        active = [index for index in range(len(self.dots)) if self.active(index)]
        lines = ["3DG1", str(len(active))]
        lines += [f"{_number(self.dot_at(index).x)} {_number(self.dot_at(index).y)} {_number(self.dot_at(index).z)}" for index in active]
        for polygon in self.polygons:
            if polygon.flags:
                lines.append(f"{len(polygon.index)} {' '.join(map(str, polygon.index))} {polygon.colour}")
        _crlf(Path(path), "\n".join(lines) + "\n")

    def export_gzs(
        self,
        path: str | Path,
        *,
        name: str | None = None,
        simplified_header: bool | None = None,
        mirror_animation: bool = False,
    ) -> None:
        name = name or self.header.name or _asm_name(Path(path))
        group_faces = [[polygon for polygon in self.polygons if polygon.flags & (1 << group)] for group in range(8)]
        groups = [group for group, faces in enumerate(group_faces) if faces]
        extra: list[Dot] = []
        overrides: dict[int, Dot] = {}
        entries: list[tuple[int, int]] = []
        for group in groups:
            vertices = [self.dot_at(index) for face in group_faces[group] for index in face.index]
            center = Dot(*( _dos(sum(getattr(dot, axis) for dot in vertices) / len(vertices)) if vertices else 0 for axis in ("x", "y", "z")))
            slot = next((i for i in range(len(self.dots)) if not self.active(i, 0) and i not in overrides), len(self.dots))
            if slot < len(self.dots):
                overrides[slot] = center
            else:
                slot = len(self.dots) + len(extra)
                extra.append(center)
            entries.append((group, slot))
        lines = self._asm_header(name, extra, overrides, simplified_header)
        lines += self._asm_points(name, extra, overrides, mirror_animation)
        lines.append(f"{name}_F")
        lines += self._vizis()
        if self.smooth_shade:
            lines += self._vertex_normals(name, extra, overrides)
        if len(groups) > 1:
            lines.append(f"\tGroups\t{len(groups)}")
            lines += [f"\tGroupP\t{slot}\t;{group}" for group, slot in entries]
            lines += [f"\tGroupF\t{name}_f{group}" for group, _ in entries]
        for group in groups:
            if len(groups) > 1:
                lines.append(f"{name}_f{group}")
            lines.append(f"\tFaces\t{len(group_faces[group])}")
            for polygon in group_faces[group]:
                lines.append(self._face(polygon))
            lines.append("\tFendQ")
        lines += ["", "\tendshape", "", "\tendc"]
        _crlf(Path(path), "\n".join(lines) + "\n")

    def export_bsp(
        self,
        path: str | Path,
        *,
        tree: bool = True,
        name: str | None = None,
        simplified_header: bool | None = None,
        mirror_animation: bool = False,
    ) -> None:
        """Write BSP assembler.

        Set ``tree=False`` to force a single ordered face list, even when the
        BSP classifier would otherwise emit ``BSP``/``BSPInit`` branches.
        """
        name = name or self.header.name or _asm_name(Path(path))
        nodes, root, flat = self._build_bsp() if tree else ([], -1, True)
        lines = (
            self._asm_header(name, [], {}, simplified_header)
            + self._asm_points(name, [], {}, mirror_animation)
            + [f"{name}_F"]
            + self._vizis()
        )
        if self.smooth_shade:
            lines += self._vertex_normals(name, [], {})
        if not tree:
            lines += ["", f"{name}_f1\tFaces"]
            lines += [self._face(polygon) for polygon in self.polygons if polygon.flags]
            lines += ["\tFend", "\tEndShape", "", "\tendc"]
        elif flat and root >= 0:
            lines += ["", f"{name}_f1\tFaces"]
            lines += self._bsp_faces(nodes, root, name, [2])
            lines += ["\tFend", "\tEndShape", "", "\tendc"]
        else:
            lines.append(f"\tBSPInit\t{name}_EBSP")
            lines += self._bsp_tree(nodes, root, name, [1])
            if root >= 0:
                lines += ["", f"{name}_f1\tFaces"] + self._bsp_faces(nodes, root, name, [2])
                lines += ["\tFendQ", f"{name}_EBSP", "\tEndShape", "", "\tendc"]
            else:
                lines += ["\tBSPEND", f"{name}_EBSP", "\tEndShape", "", "\tendc"]
        _crlf(Path(path), "\n".join(lines) + "\n")

    def _asm_header(self, name: str, extra: list[Dot], overrides: dict[int, Dot], simplified_header: bool | None = None) -> list[str]:
        # Match asm_bounds() in the C exporter: header dimensions cover every
        # active source dot in every animation frame. Appended group centres
        # are static auxiliary points and are considered once.
        points = [
            self._asm_dot(index, frame, extra, overrides)
            for frame in range(self.frame_count)
            for index in range(len(self.dots))
            if self._asm_active(index, frame, extra, overrides)
        ]
        points.extend(extra)
        radius = max((_length(_xyz(point)) for point in points), default=0)
        xs = max((abs(point.x) for point in points), default=0)
        ys = max((abs(point.y) for point in points), default=0)
        zs = max((abs(point.z) for point in points), default=0)
        source = str(self.source) if self.source else "SHAPED"
        header = self.header
        simplified = header.simplified if simplified_header is None else simplified_header
        fields = [f"{name}_P", "0", f"{name}_F", "0", str(header.zsort_priority), "0", "0", str(header.scale), str(header.colbox),
                  f"{xs:.0f}", f"{ys:.0f}", f"{zs:.0f}", f"{radius:.0f}", str(header.colour_table), str(header.shadow)]
        if not simplified:
            fields += [str(header.simple1), str(header.simple2), str(header.simple3)]
        fields.append(f"<{name}>")
        return [f";--Shape file ----- {name} ---- Generated with FastFX", "\tifne\tDO_HDR", "", name, f"\tShapeHdr\t{','.join(fields)}", "\telseif"]

    def _asm_dot(self, index: int, frame: int, extra: list[Dot], overrides: dict[int, Dot]) -> Dot:
        if index in overrides:
            return overrides[index]
        return self.dot_at(index, frame) if index < len(self.dots) else extra[index - len(self.dots)]

    def _asm_active(self, index: int, frame: int, extra: list[Dot], overrides: dict[int, Dot]) -> bool:
        return index in overrides or index >= len(self.dots) or self.active(index, frame)

    def _asm_points(
        self,
        name: str,
        extra: list[Dot],
        overrides: dict[int, Dot],
        mirror_animation: bool = False,
    ) -> list[str]:
        count = len(self.dots) + len(extra)
        frames = self.frame_count
        kind = [0] * count
        for i in range(count):
            if self._asm_active(i, 0, extra, overrides):
                kind[i] = 2
                base = self._asm_dot(i, 0, extra, overrides)
                if any(_xyz(self._asm_dot(i, frame, extra, overrides)) != _xyz(base) for frame in range(1, frames)):
                    kind[i] |= 1
        i = 0
        while i < count:
            mirrored = i + 1 < count and kind[i] & 2 and kind[i + 1] & 2 and all(
                (lambda a, b: a.x == -b.x and a.y == b.y and a.z == b.z and self._asm_active(i, frame, extra, overrides) and self._asm_active(i + 1, frame, extra, overrides))(self._asm_dot(i, frame, extra, overrides), self._asm_dot(i + 1, frame, extra, overrides)) for frame in range(frames))
            if mirrored: i += 2
            else: kind[i] &= ~2; i += 1
        width = "w" if max((_length(_xyz(self._asm_dot(i, 0, extra, overrides))) for i in range(count)), default=0) > 127 else "b"
        lines = [f"{name}_P"]
        pos = 0; block = 0
        while pos < count:
            animated = bool(kind[pos] & 1); end = pos + 1
            while end < count and bool(kind[end] & 1) == animated: end += 1
            if not animated:
                lines += self._point_run(width, kind, pos, end, 0, extra, overrides)
            else:
                letter = chr(ord("A") + block); block += 1
                frame_order = list(range(frames))
                if mirror_animation and frames > 2:
                    frame_order.extend(range(frames - 2, 0, -1))
                lines.append(f"\tFrames\t{len(frame_order)}")
                lines += [f"\tjumptab\t.A{frame}{letter}" for frame in frame_order]
                for frame in range(frames):
                    run = self._point_run(width, kind, pos, end, frame, extra, overrides)
                    run[0] = f".A{frame}{letter}" + run[0]
                    lines += run
                    if frame + 1 < frames: lines.append(f"\tjump\t.EB{block - 1}")
                lines.append(f".EB{block - 1}")
            pos = end
        return lines + ["", "\tEndPoints"]

    def _point_run(self, width: str, kind: list[int], start: int, end: int, frame: int, extra: list[Dot], overrides: dict[int, Dot]) -> list[str]:
        lines: list[str] = []; pos = start
        while pos < end:
            mirrored = bool(kind[pos] & 2); stop = pos + 1
            while stop < end and bool(kind[stop] & 2) == mirrored: stop += 1
            lines.append(f"\tPointsX{width}\t{(stop - pos) // 2}" if mirrored else f"\tPoints{width}\t{stop - pos}")
            step = 2 if mirrored else 1
            for i in range(pos, stop, step):
                d = self._asm_dot(i, frame, extra, overrides)
                lines.append(f"\tp{width}\t{int(_dos(-d.x))},{int(_dos(-d.y))},{int(_dos(d.z))}\t;{i}{'' if self._asm_active(i, frame, extra, overrides) else '  **'}")
            pos = stop
        return lines

    def _vizis(self) -> list[str]:
        usable = [p for p in self.polygons if p.flags and len(p.index) > 2]
        lines = [f"\tVizis\t{len(usable) or 1}"]
        lines += [f"\tViz\t{p.index[0]},{p.index[1]},{p.index[2]}\t;{self._polygon_index(p)}" for p in usable]
        return lines if usable else lines + ["\tViz\t0,0,0\t; 0"]

    def _face(self, polygon: Polygon) -> str:
        n = self._normal(polygon)
        return f"\tFace{len(polygon.index)}\t{polygon.colour},{self._vizi(polygon)},{n[0]:.0f},{n[1]:.0f},{n[2]:.0f}" + "".join(f",{i}" for i in polygon.index)

    def _vizi(self, polygon: Polygon) -> int:
        index = self._polygon_index(polygon)
        return -1 if len(polygon.index) <= 2 else sum(1 for p in self.polygons[:index] if p.flags and len(p.index) > 2)

    def _polygon_index(self, polygon: Polygon) -> int:
        return next(index for index, candidate in enumerate(self.polygons) if candidate is polygon)

    def _normal(self, polygon: Polygon) -> tuple[float, float, float]:
        if len(polygon.index) < 3: return (0, 0, 0)
        a, b, c = (self.dot_at(i) for i in polygon.index[:3]); normal = _cross(_sub(_xyz(b), _xyz(a)), _sub(_xyz(c), _xyz(a))); length = _length(normal)
        return tuple(0 if abs(value) < 1e-7 else value * 127 / length for value in normal) if length else (0, 0, 0)

    def _vertex_normals(self, name: str, extra: list[Dot], overrides: dict[int, Dot]) -> list[str]:
        extent = len(self.dots) + len(extra); lines = [f"{name}_VN\t\t;Vertex normals", f"\tVNORMALS\t{extent}"]
        for dot in range(extent):
            adjacent = [p for p in self.polygons if p.flags and dot in p.index]
            total = tuple(sum(self._normal(p)[axis] for p in adjacent) for axis in range(3)); length = _length(total)
            normal = (total[0] * 127 / length, -total[1] * 127 / length, -total[2] * 127 / length) if length > 1e-4 else (0, 0, 0)
            lines.append(f"\tVN\t{normal[0]:.0f},{normal[1]:.0f},{normal[2]:.0f}\t;{dot}-({len(adjacent)})")
        return lines

    def _plane(self, index: int) -> tuple[float, float, float, float] | None:
        p = self.polygons[index]
        if len(p.index) < 3: return None
        a, b, c = (self.dot_at(i) for i in p.index[:3]); n = _cross(_sub(_xyz(b), _xyz(a)), _sub(_xyz(c), _xyz(a))); length = _length(n)
        if length < 1e-12: return None
        n = tuple(x / length for x in n); return (*n, -_dot(n, _xyz(a)))

    def _classify(self, index: int, plane: tuple[float, float, float, float], weight: float) -> tuple[int, float]:
        sides = [_dot(plane[:3], _xyz(self.dot_at(i))) + plane[3] for i in self.polygons[index].index]
        front, back = any(x > weight for x in sides), any(x < -weight for x in sides)
        return (2 if front and back else 1 if front else -1 if back else 0), (sum(sides) / len(sides) if sides else 0)

    def _build_bsp(self) -> tuple[list[_BspNode], int, bool]:
        nodes: list[_BspNode] = []; flat = [True]
        items = [i for i, p in enumerate(self.polygons) if p.flags and len(p.index) >= 2]
        radius = max((_length(_xyz(self.dot_at(i))) for i in range(len(self.dots))), default=0); weight = radius / 30
        def leaves(values: list[int], flags: list[int] | None = None) -> int:
            if flags is not None:
                order: list[int] = []
                for phase in range(5):
                    for item, flag in zip(values, flags):
                        high = flag & 0xF000
                        match = (phase == 0 and high == 0x4000) or (phase == 1 and flag & 0x9000 == 0x1000) or (phase == 2 and high == 0x6000) or (phase == 3 and high == 0) or (phase == 4 and high == 0x2000)
                        if match and item not in order: order.append(item)
                values = order + [item for item in values if item not in order]
            root = tail = -1
            for item in values:
                node = len(nodes); nodes.append(_BspNode(item))
                if root < 0: root = node
                else: nodes[tail].front = node
                tail = node
            return root
        def build(values: list[int], depth: int) -> int:
            if not values: return -1
            flags = [0] * len(values)
            for a in range(len(values)):
                for b in range(a + 1, len(values)):
                    pa, pb = self._plane(values[a]), self._plane(values[b])
                    if not pa or not pb: continue
                    ab, _ = self._classify(values[a], pb, weight); ba, _ = self._classify(values[b], pa, weight)
                    af, ak, bf, bk = ab in (1, 2), ab in (-1, 2), ba in (1, 2), ba in (-1, 2)
                    if ab == 2 and ba == 2: flags[a] |= 0x7000; flags[b] |= 0x7000
                    elif ab == 2: flags[b] |= 0x1000 | (0x2000 if bf else 0) | (0x4000 if bk else 0); flags[a] |= 0x4000 if bf else 0x2000
                    elif ba == 2: flags[a] |= 0x1000 | (0x2000 if af else 0) | (0x4000 if ak else 0); flags[b] |= 0x4000 if af else 0x2000
                    elif af and not bf: flags[a] |= 0x2000; flags[b] |= 0x4000
                    elif bf and not af: flags[b] |= 0x2000; flags[a] |= 0x4000
            candidates = [i for i, flag in enumerate(flags) if flag & 0xF000 == 0x6000]
            if not candidates or depth >= MAX_POLYS: return leaves(values, flags)
            best = max(candidates, key=lambda i: _length(_cross(_sub(_xyz(self.dot_at(self.polygons[values[i]].index[1])), _xyz(self.dot_at(self.polygons[values[i]].index[0]))), _sub(_xyz(self.dot_at(self.polygons[values[i]].index[2])), _xyz(self.dot_at(self.polygons[values[i]].index[0]))))) * (25 if self.polygons[values[i]].type & 0x20 else 1))
            flat[0] = False; splitter = values[best]; node = len(nodes); nodes.append(_BspNode(splitter, leaf=False)); plane = self._plane(splitter)
            if not plane: return node
            front: list[int] = []; back: list[int] = []
            for i, item in enumerate(values):
                if i == best: continue
                side, center = self._classify(item, plane, weight)
                (front if (center >= 0 if side in (0, 2) else side > 0) else back).append(item)
            nodes[node].front = build(front, depth + 1); nodes[node].back = build(back, depth + 1); return node
        return nodes, build(items, 0), flat[0]

    def _bsp_tree(self, nodes: list[_BspNode], node: int, name: str, number: list[int]) -> list[str]:
        if node < 0: return []
        n = nodes[node]; face = number[0]
        if n.leaf:
            if n.front >= 0: return self._bsp_tree(nodes, n.front, name, number)
            number[0] += 1; return [f"\tBSPE\t{name}_f{face}"]
        if n.front < 0 and n.back < 0: number[0] += 1; return [f"\tBSPE\t{name}_f{face}"]
        if n.front >= 0:
            branch = face + 1; number[0] += 2; lines = [f"\tBSP\t{self._vizi(self.polygons[n.poly])},{name}_f{face},.bsp{branch}"]
            lines += self._bsp_tree(nodes, n.back, name, number) if n.back >= 0 else ["\tBSPEND"]
            lines.append(f".bsp{branch}"); return lines + self._bsp_tree(nodes, n.front, name, number)
        number[0] += 1; lines = [f"\tBSPNULL\t{self._vizi(self.polygons[n.poly])},{name}_f{face}"]
        return lines + (self._bsp_tree(nodes, n.back, name, number) if n.back >= 0 else ["\tBSPEND"])

    def _bsp_faces(self, nodes: list[_BspNode], node: int, name: str, number: list[int]) -> list[str]:
        if node < 0: return []
        n = nodes[node]; lines = [self._face(self.polygons[n.poly])]
        if n.leaf: return lines + self._bsp_faces(nodes, n.front, name, number)
        if n.front >= 0: number[0] += 1
        if n.back >= 0:
            face = number[0]; number[0] += 1; lines += ["\tFendQ", f"{name}_f{face}\tFaces"] + self._bsp_faces(nodes, n.back, name, number)
        if n.front >= 0:
            face = number[0]; number[0] += 1; lines += ["\tFendQ", f"{name}_f{face}\tFaces"] + self._bsp_faces(nodes, n.front, name, number)
        return lines


def load(path: str | Path) -> Shape:
    path = Path(path)
    # DOS text files commonly use Ctrl-Z (0x1A) as an end-of-file marker.
    # Treat the first marker as EOF before decoding or tokenizing, including
    # when it follows an otherwise valid final polygon record.
    data = path.read_bytes().split(b"\x1a", 1)[0]
    lines = data.decode("ascii").replace("\r\n", "\n").splitlines()
    if not lines: raise FormatError("empty shape file")
    magic = lines[0].strip(); body = lines[1:]
    if magic == "3DG1": shape = _load_3dg1(body)
    elif magic == "3DCG": shape = _load_3dcg(body)
    elif magic == "3DAN": shape = _load_3dan(body)
    elif magic == "3DA1": shape = _load_3da1(body)
    else: raise FormatError(f"unsupported shape signature: {magic}")
    shape.source = path; return shape


def load_colour_tables(shape: Shape, path: str | Path = "COLTABS.DAT") -> None:
    """Apply the C exporter's selected default colour-table behavior.

    The native CLI selects the first ``COLTAB`` record. A negative value turns
    on the per-vertex normal block in GZS and BSP output.
    """
    try:
        records = Path(path).read_text(encoding="ascii").splitlines()
    except FileNotFoundError:
        return
    for record in records:
        fields = record.split()
        if len(fields) == 3 and fields[0] == "COLTAB":
            shape.header.colour_table = fields[1]
            shape.smooth_shade = int(fields[2]) < 0
            return


def write(
    shape: Shape,
    path: str | Path,
    format: Literal["gzs", "bsp", "internal", "3dg1"],
    *,
    tree: bool = True,
    name: str | None = None,
    simplified_header: bool | None = None,
    mirror_animation: bool = False,
) -> None:
    match format.lower():
        case "gzs": shape.export_gzs(path, name=name, simplified_header=simplified_header, mirror_animation=mirror_animation)
        case "bsp": shape.export_bsp(path, tree=tree, name=name, simplified_header=simplified_header, mirror_animation=mirror_animation)
        case "internal": shape.save_internal(path)
        case "3dg1": shape.save_3dg1(path)
        case _: raise ValueError(f"unsupported export format: {format}")


def _load_3dg1(lines: list[str]) -> Shape:
    count = int(lines[0]); _check(count, MAX_DOTS); dots = [Dot(*map(_dos, map(float, lines[i + 1].split()))) for i in range(count)]; polygons = []
    for line in lines[count + 1:]:
        values = list(map(int, line.split())); n = values[0]; _check(n, MAX_POLY_VERTS); polygons.append(Polygon(values[1:1 + n], values[1 + n]))
    return Shape(dots, polygons, [[FrameDot(d.x, d.y, d.z) for d in dots]])


def _load_3dcg(lines: list[str]) -> Shape:
    dots_count, frames_count = map(int, lines[0].split()); _check(dots_count, MAX_DOTS); _check(frames_count, MAX_FRAMES); cursor = 1; frames: list[list[FrameDot]] = []
    for _ in range(frames_count):
        frame = []
        for _ in range(dots_count):
            xyz, active = lines[cursor].split(","); cursor += 1; x, y, z = map(float, xyz.split()); frame.append(FrameDot(_dos(x), _dos(y), _dos(z), int(active)))
        frames.append(frame)
    dots = [Dot(d.x, d.y, d.z, bool(d.active & 0x100)) for d in frames[0]]; polygons = []
    for line in lines[cursor:]:
        fields = line.replace(",", " , ").split(); n = int(fields[0]); _check(n, MAX_POLY_VERTS); indices = list(map(int, fields[1:1+n])); colour = int(fields[n + 2], 0); flags = int(fields[n + 3], 0); type_ = int(fields[n + 4], 0); polygons.append(Polygon(indices, colour, flags & ~0x100, type_, bool(flags & 0x100)))
    polygons.reverse(); return Shape(dots, polygons, frames)


def _load_3dan(lines: list[str]) -> Shape:
    # The DOS reader uses fscanf("%u %u"), so the two header counts and all
    # following coordinates are whitespace-delimited rather than line-bound.
    # In particular, valid files commonly put the dot and frame counts on
    # separate lines.
    tokens = " ".join(lines).split()
    if len(tokens) < 2:
        raise FormatError("incomplete 3DAN header")
    dots_count, frames_count = map(int, tokens[:2])
    _check(dots_count, MAX_DOTS)
    _check(frames_count, MAX_FRAMES)
    cursor = 2
    frames: list[list[FrameDot]] = []
    try:
        for _ in range(frames_count):
            frame = []
            for _ in range(dots_count):
                x, y, z = map(float, tokens[cursor:cursor + 3])
                cursor += 3
                frame.append(FrameDot(_dos(x), _dos(y), _dos(z)))
            frames.append(frame)
        polygons: list[Polygon] = []
        while cursor < len(tokens):
            count = int(tokens[cursor])
            cursor += 1
            _check(count, MAX_POLY_VERTS)
            indices = list(map(int, tokens[cursor:cursor + count]))
            if len(indices) != count:
                raise FormatError("incomplete 3DAN polygon")
            cursor += count
            packed = int(tokens[cursor], 0)
            cursor += 1
            polygons.append(Polygon(indices, packed & 0xFF, 1, (packed >> 1) or 7))
    except (IndexError, ValueError) as error:
        raise FormatError("invalid or incomplete 3DAN data") from error
    return Shape([Dot(d.x, d.y, d.z) for d in frames[0]], polygons, frames)


def _load_3da1(lines: list[str]) -> Shape:
    fixed = int(re.fullmatch(r"POINTS:(\d+)", lines[0].strip()).group(1)); _check(fixed, MAX_DOTS); cursor = 1; base = []
    for _ in range(fixed):
        x, y, z = map(float, lines[cursor].split()); cursor += 1; base.append(Dot(_dos(x), _dos(-y), _dos(z)))
    match = re.fullmatch(r"ANIM:(\d+)\s+(\d+)", lines[cursor].strip());
    if not match: raise FormatError("invalid 3DA1 ANIM header")
    animated, frame_count = map(int, match.groups()); cursor += 1; _check(fixed + animated, MAX_DOTS); _check(frame_count, MAX_FRAMES); frames = []
    for _ in range(frame_count):
        if not lines[cursor].strip().startswith("FRAME:"): raise FormatError("invalid 3DA1 frame")
        cursor += 1; frame = [FrameDot(d.x, d.y, d.z) for d in base]
        for _ in range(animated):
            x, y, z = map(float, lines[cursor].split()); cursor += 1; frame.append(FrameDot(_dos(x), _dos(-y), _dos(z)))
        frames.append(frame)
    match = re.fullmatch(r"FACES:(\d+)", lines[cursor].strip());
    if not match: raise FormatError("invalid 3DA1 face header")
    cursor += 1; polygons = _packed_polygons(lines[cursor:], True, True); return Shape([Dot(d.x, d.y, d.z) for d in frames[0]], polygons, frames)


def _packed_polygons(lines: Iterable[str], reverse: bool, sams: bool) -> list[Polygon]:
    types = (7, 5, 7, 5, 3, 1, 3, 1, 15, 13, 15, 13, 11, 9, 11, 9); result = []
    for line in lines:
        parts = list(map(lambda x: int(x, 0), line.split())); n = parts[0]; _check(n, MAX_POLY_VERTS); indices = parts[1:1+n]; packed = parts[1+n]
        if reverse: indices.reverse()
        result.append(Polygon(indices, packed if sams else packed & 0xFF, 1, types[packed >> 1] if sams and 0 <= packed >> 1 < 16 else (packed >> 1 or 7)))
    return result


def _check(value: int, maximum: int) -> None:
    if value < 0 or value > maximum: raise FormatError("SHAPED capacity exceeded")


def _xyz(dot: Dot | FrameDot) -> tuple[float, float, float]: return dot.x, dot.y, dot.z
def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]: return a[0]-b[0], a[1]-b[1], a[2]-b[2]
def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float: return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]: return a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]
def _length(value: tuple[float, float, float]) -> float: return sqrt(_dot(value, value))
def _asm_name(path: Path) -> str: return path.stem[:62] or "S"
