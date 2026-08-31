import math
from dataclasses import dataclass

# FastFX
# File: bsp_tree.py
# BSP tree logic ported from SHAPED.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

@dataclass
class BspNode:
    poly: int = -1
    front: int = -1
    back: int = -1
    leaf: int = 1


class BspTreeBuilder:
    """Port of the SHAPED BSP logic used for ASM BSP export.

    The reference C exporter supports faces with a minimum of 2 points. That rule is
    preserved here: 2-point edges are accepted as leaves, but not as splitter planes.
    """

    MAX_POLYS = 500

    def __init__(self, vertices, polys, *, plane_weight=None, diag_mode=0):
        self.vertices = list(vertices)
        self.polys = [self._normalize_poly(poly) for poly in polys]
        self.plane_weight = plane_weight if plane_weight is not None else self._default_plane_weight()
        self.diag_mode = diag_mode
        self.nodes = []
        self.root = -1
        self.spanning = 0
        self.flat = 1
        self.valid = False

    @staticmethod
    def _normalize_poly(poly):
        if isinstance(poly, dict):
            count = int(poly.get('count', len(poly.get('indices', []))))
            normalized = dict(poly)
            normalized['count'] = count
            return normalized
        if isinstance(poly, (list, tuple)):
            return {'indices': list(poly), 'count': len(poly), 'flags': 1, 'type': 0}
        raise TypeError(f'Unsupported polygon format: {type(poly)!r}')

    @staticmethod
    def _poly_indices(poly):
        if isinstance(poly, dict):
            return list(poly.get('indices', ()))
        return list(poly)

    @staticmethod
    def _poly_count(poly):
        if isinstance(poly, dict):
            return int(poly.get('count', len(poly.get('indices', []))))
        return len(poly)

    def _default_plane_weight(self):
        if not self.vertices:
            return 1.0
        max_radius = 0.0
        for x, y, z in self.vertices:
            r = math.sqrt((x * x) + (y * y) + (z * z))
            if r > max_radius:
                max_radius = r
        return max_radius / 30.0 if max_radius else 1.0

    @staticmethod
    def polygon_plane(poly, vertices):
        """Return a normalized plane [nx, ny, nz, d] for a triangle or higher polygon."""
        count = BspTreeBuilder._poly_count(poly)
        if count < 3:
            return None
        indices = BspTreeBuilder._poly_indices(poly)
        if len(indices) < 3:
            return None
        a = vertices[indices[0]]
        b = vertices[indices[1]]
        c = vertices[indices[2]]
        ax, ay, az = a
        bx, by, bz = b
        cx, cy, cz = c

        plane = [
            (by - ay) * (cz - az) - (bz - az) * (cy - ay),
            (bz - az) * (cx - ax) - (bx - ax) * (cz - az),
            (bx - ax) * (cy - ay) - (by - ay) * (cx - ax),
            0.0,
        ]
        length = math.sqrt((plane[0] * plane[0]) + (plane[1] * plane[1]) + (plane[2] * plane[2]))
        if length < 1e-12:
            return None
        plane[0] /= length
        plane[1] /= length
        plane[2] /= length
        plane[3] = -(plane[0] * ax + plane[1] * ay + plane[2] * az)
        return plane

    @staticmethod
    def classify_poly(poly, plane, vertices, plane_weight=0.0, return_centroid_side=False):
        """Classify a polygon relative to a plane, matching SHAPED's front/back/spanning logic."""
        count = BspTreeBuilder._poly_count(poly)
        indices = BspTreeBuilder._poly_indices(poly)
        front = False
        back = False
        total = 0.0

        for index in indices:
            x, y, z = vertices[index]
            side = plane[0] * x + plane[1] * y + plane[2] * z + plane[3]
            total += side
            if side > plane_weight:
                front = True
            elif side < -plane_weight:
                back = True

        centroid_side = total / count if count else 0.0
        if front and back:
            classification = 2
        elif front:
            classification = 1
        elif back:
            classification = -1
        else:
            classification = 0

        if return_centroid_side:
            return classification, centroid_side
        return classification

    @staticmethod
    def bsp_splitter_score(poly, vertices):
        """Score a polygon as a BSP splitter, as in SHAPED's reference exporter."""
        count = BspTreeBuilder._poly_count(poly)
        if count < 3:
            return -1.0
        indices = BspTreeBuilder._poly_indices(poly)
        a = vertices[indices[0]]
        b = vertices[indices[1]]
        c = vertices[indices[2]]
        ux = b[0] - a[0]
        uy = b[1] - a[1]
        uz = b[2] - a[2]
        vx = c[0] - a[0]
        vy = c[1] - a[1]
        vz = c[2] - a[2]
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        score = math.sqrt((nx * nx) + (ny * ny) + (nz * nz))
        poly_type = int(poly.get('type', 0)) if isinstance(poly, dict) else 0
        return score * (25.0 if (poly_type & 0x20) else 1.0)

    def bsp_relation_flags(self, items, count, out_flags):
        """Compute relation flags between all polygons in a BSP working set."""
        spanning = 0
        for i in range(count):
            out_flags[i] = 0
        for a in range(count):
            for b in range(a + 1, count):
                pa = self.polygon_plane(self.polys[items[a]], self.vertices)
                pb = self.polygon_plane(self.polys[items[b]], self.vertices)
                if pa is None or pb is None:
                    continue
                ab, ca = self.classify_poly(self.polys[items[a]], pb, self.vertices, self.plane_weight, return_centroid_side=True)
                ba, cb = self.classify_poly(self.polys[items[b]], pa, self.vertices, self.plane_weight, return_centroid_side=True)
                af = ab == 1 or ab == 2
                ak = ab == -1 or ab == 2
                bf = ba == 1 or ba == 2
                bk = ba == -1 or ba == 2
                if ab == 2 or ba == 2:
                    spanning += 1
                if ab == 2 and ba == 2:
                    out_flags[a] |= 0x7000
                    out_flags[b] |= 0x7000
                    continue
                if ab == 2:
                    out_flags[b] |= (0x1000 | (0x2000 if bf else 0) | (0x4000 if bk else 0))
                    out_flags[a] |= (0x4000 if bf else 0x2000)
                elif ba == 2:
                    out_flags[a] |= (0x1000 | (0x2000 if af else 0) | (0x4000 if ak else 0))
                    out_flags[b] |= (0x4000 if af else 0x2000)
                elif af and not bf:
                    out_flags[a] |= 0x2000
                    out_flags[b] |= 0x4000
                elif bf and not af:
                    out_flags[b] |= 0x2000
                    out_flags[a] |= 0x4000
        return spanning

    def build_bsp_leaf_list(self, items, count):
        root = -1
        tail = -1
        for i in range(count):
            if self.count >= self.MAX_POLYS:
                break
            node_index = self.count
            self.count += 1
            self.nodes.append(BspNode(poly=items[i], front=-1, back=-1, leaf=1))
            if root < 0:
                root = node_index
            else:
                self.nodes[tail].front = node_index
            tail = node_index
        return root

    def build_bsp_leaf_list_ordered(self, items, count, flags):
        ordered = []
        emitted = [False] * count

        for phase in range(5):
            for i in range(count):
                high = flags[i] & 0xF000
                matches = (
                    (phase == 0 and high == 0x4000) or
                    (phase == 1 and (flags[i] & 0x9000) == 0x1000) or
                    (phase == 2 and high == 0x6000) or
                    (phase == 3 and high == 0) or
                    (phase == 4 and high == 0x2000)
                )
                if matches and not emitted[i]:
                    ordered.append(items[i])
                    emitted[i] = True

        for i in range(count):
            if not emitted[i]:
                ordered.append(items[i])

        return self.build_bsp_leaf_list(ordered, len(ordered))

    def build_bsp_level(self, items, count, depth):
        if count <= 0 or self.count >= self.MAX_POLYS:
            return -1

        flags = [0] * count
        self.spanning += self.bsp_relation_flags(items, count, flags)

        if self.diag_mode == 2:
            for i in range(count):
                if (flags[i] & 0x7000) == 0x7000:
                    poly = self.polys[items[i]]
                    poly['selected'] = 1
        if self.diag_mode == 3:
            for i in range(count):
                if flags[i] & 0x1000:
                    poly = self.polys[items[i]]
                    poly['selected'] = 1

        best_index = -1
        best_score = -1.0
        for i in range(count):
            if (flags[i] & 0xF000) == 0x6000:
                score = self.bsp_splitter_score(self.polys[items[i]], self.vertices)
                if score > best_score:
                    best_score = score
                    best_index = i

        if best_index < 0 or depth >= self.MAX_POLYS:
            return self.build_bsp_leaf_list_ordered(items, count, flags)

        splitter = items[best_index]
        node_index = self.count
        self.count += 1
        self.nodes.append(BspNode(poly=splitter, front=-1, back=-1, leaf=0))

        plane = self.polygon_plane(self.polys[splitter], self.vertices)
        if plane is None:
            self.nodes[node_index].leaf = 1
            return node_index

        fronts = []
        backs = []
        for i in range(count):
            if i == best_index:
                continue
            side_poly = self.polys[items[i]]
            side, centroid_side = self.classify_poly(side_poly, plane, self.vertices, self.plane_weight, return_centroid_side=True)
            if side == 2 or side == 0:
                side = 1 if centroid_side >= 0 else -1
            if side > 0:
                fronts.append(items[i])
            else:
                backs.append(items[i])

        self.nodes[node_index].front = self.build_bsp_level(fronts, len(fronts), depth + 1)
        self.nodes[node_index].back = self.build_bsp_level(backs, len(backs), depth + 1)
        return node_index

    def build(self):
        self.nodes = []
        self.count = 0
        self.spanning = 0
        self.flat = 1
        items = []
        for index, poly in enumerate(self.polys):
            poly_count = self._poly_count(poly)
            if poly_count >= 2 and poly.get('flags', 0):
                items.append(index)

        self.root = self.build_bsp_level(items, len(items), 0)
        self.valid = True
        return self.root

    @property
    def node_count(self):
        return len(self.nodes)

    @staticmethod
    def bsp_splitter_score(poly, vertices):
        return BspTreeBuilder._bsp_splitter_score_static(poly, vertices)

    @staticmethod
    def _bsp_splitter_score_static(poly, vertices):
        return BspTreeBuilder.bsp_splitter_score(poly, vertices)


__all__ = ['BspNode', 'BspTreeBuilder']
