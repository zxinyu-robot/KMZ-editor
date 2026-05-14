# -*- coding: utf-8 -*-
"""build_llh_enu_transform 往返与参考点零检（unittest）。

运行: cd backend && PYTHONPATH=. python -m unittest app.utils.path_editor.test_coordinates_llh_enu -v
"""
from __future__ import annotations

import unittest

from app.utils.path_editor.geometry.coordinates import build_llh_enu_transform


class TestLlhEnuTransform(unittest.TestCase):
    def test_origin_zero(self) -> None:
        ref_lon, ref_lat, ref_alt = 120.0, 30.0, 100.0
        llh_to_enu, _ = build_llh_enu_transform(ref_lon, ref_lat, ref_alt)
        e, n, u = llh_to_enu(ref_lon, ref_lat, ref_alt)
        self.assertLess(abs(e) + abs(n) + abs(u), 1e-2, "参考点应在 ENU 原点附近")

    def test_roundtrip(self) -> None:
        ref_lon, ref_lat, ref_alt = 120.0, 30.0, 0.0
        llh_to_enu, enu_to_llh = build_llh_enu_transform(ref_lon, ref_lat, ref_alt)
        lon, lat, alt = 120.01, 30.02, 125.5
        e, n, u = llh_to_enu(lon, lat, alt)
        lon2, lat2, alt2 = enu_to_llh(e, n, u)
        self.assertAlmostEqual(lon2, lon, places=6)
        self.assertAlmostEqual(lat2, lat, places=6)
        self.assertAlmostEqual(alt2, alt, places=3)


if __name__ == "__main__":
    unittest.main()
