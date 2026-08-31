import importlib.util
import sys
import types
import unittest
from pathlib import Path

# Avoid importing the full Blender addon when running the standalone builder unit tests.
package = types.ModuleType('fastfx')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'fastfx')]
sys.modules['fastfx'] = package

module_path = Path(__file__).resolve().parents[1] / 'fastfx' / 'bsp_tree.py'
spec = importlib.util.spec_from_file_location('fastfx.bsp_tree', module_path)
module = importlib.util.module_from_spec(spec)
sys.modules['fastfx.bsp_tree'] = module
spec.loader.exec_module(module)

BspTreeBuilder = module.BspTreeBuilder


class BspTreeBuilderTests(unittest.TestCase):
    def test_polygon_plane_for_triangle(self):
        vertices = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
        poly = {'indices': [0, 1, 2], 'flags': 1, 'type': 0, 'count': 3}

        plane = BspTreeBuilder.polygon_plane(poly, vertices)

        self.assertIsNotNone(plane)
        self.assertAlmostEqual(plane[0], 0.0)
        self.assertAlmostEqual(plane[1], 0.0)
        self.assertAlmostEqual(plane[2], 1.0)
        self.assertAlmostEqual(plane[3], 0.0)

    def test_classify_poly_handles_front_back_and_spanning(self):
        vertices = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 0.0, 1.0),
            (0.0, 1.0, 1.0),
            (0.0, 0.0, -1.0),
            (1.0, 0.0, -1.0),
            (0.0, 1.0, -1.0),
        ]
        splitter = {'indices': [0, 1, 2], 'flags': 1, 'type': 0, 'count': 3}
        front = {'indices': [3, 4, 5], 'flags': 1, 'type': 0, 'count': 3}
        back = {'indices': [6, 7, 8], 'flags': 1, 'type': 0, 'count': 3}

        plane = BspTreeBuilder.polygon_plane(splitter, vertices)

        self.assertEqual(BspTreeBuilder.classify_poly(front, plane, vertices), 1)
        self.assertEqual(BspTreeBuilder.classify_poly(back, plane, vertices), -1)

    def test_two_point_faces_are_accepted_by_the_builder(self):
        vertices = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
        ]
        polys = [
            {'indices': [0, 1], 'flags': 1, 'type': 0, 'count': 2},
        ]

        builder = BspTreeBuilder(vertices, polys)
        items = builder.build()

        self.assertNotEqual(items, -1)
        self.assertEqual(builder.node_count, 1)


if __name__ == '__main__':
    unittest.main()
