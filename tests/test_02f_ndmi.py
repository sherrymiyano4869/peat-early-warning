"""Uji NDMI 02f dengan Earth Engine TIRUAN yang menolak urutan panggilan yang salah seperti Earth Engine asli.

    python tests/test_02f_ndmi.py

Memeriksa: (1) komposit median() tanpa proyeksi bawaan ditolak oleh reduceResolution (galat yang pernah terjadi di v0.19),
(2) fetch_ndmi_tile menetapkan proyeksi bawaan SEBELUM reduceResolution, (3) cadangan proyeksi asli B11 bila cara pertama ditolak server,
(4) galat lain diteruskan, (5) piksel NODATA (-9999, tertutup awan) tidak menjadi NDMI 0 di tabel sel.
Tiruan ini bukan Earth Engine: ia hanya menegakkan aturan yang sudah diketahui. Tetap uji pada Earth Engine sungguhan dengan satu jendela dulu.
"""
import importlib.util
import sys
from datetime import date
from pathlib import Path

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.cells import cell_grid_lonlat  # noqa: E402
from src.grid import to_grid  # noqa: E402

spec = importlib.util.spec_from_file_location("f02", ROOT / "scripts" / "02f_grid_dynamic.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class EEException(Exception):
    pass


class Proj:
    def __init__(self, kind):
        self.kind = kind


class Img:
    def __init__(self, proj=None, ops=()):
        self.proj, self.ops = proj, tuple(ops)

    def _n(self, op, proj="keep"):
        return Img(self.proj if proj == "keep" else proj, self.ops + (op,))

    def select(self, name):
        return Img(Proj("native") if name == "B11" else self.proj, self.ops + (f"select:{name}",))

    def gte(self, v): return self._n("gte")
    def updateMask(self, mk): return self._n("updateMask")
    def normalizedDifference(self, bands): assert bands == ["B8", "B11"]; return self._n("nd")
    def rename(self, n): return self._n("rename")
    def projection(self): return self.proj

    def setDefaultProjection(self, crs=None, crsTransform=None, scale=None):
        if isinstance(crs, Proj):
            return self._n("setDefaultProjection", crs)
        assert crs == "EPSG:4326" and scale == 20
        return self._n("setDefaultProjection", Proj("geographic"))

    def reduceResolution(self, reducer, maxPixels):
        if self.proj is None:
            raise EEException("Image.reduceResolution: The input to reduceResolution does not have a valid default projection. Use setDefaultProjection() first.")
        return self._n("reduceResolution")

    def reproject(self, crs, scale): return self._n("reproject")
    def toFloat(self): return self._n("toFloat")
    def unmask(self, v): assert v == -9999.0; return self._n("unmask")

    def getDownloadURL(self, params):
        if STATE["reject_geographic"] and self.proj.kind == "geographic":
            raise EEException("getDownloadURL: projection tidak valid (uji)")
        if STATE["other_error"]:
            raise EEException("Computation timed out.")
        STATE["log"].append(self.ops)
        return "http://unduh/ndmi.tif"


class Coll:
    def filterBounds(self, g): return self
    def filterDate(self, a, b): return self
    def size(self): return type("S", (), {"getInfo": lambda s: 3})()
    def linkCollection(self, other, bands): return self
    def map(self, fn): fn(Img(Proj("native"))); return self
    def median(self): return Img(None, ("median",))      # tanpa proyeksi bawaan, seperti Earth Engine asli
    def first(self): return Img(Proj("native"))


class FakeEE:
    EEException = EEException
    class Geometry:
        Rectangle = staticmethod(lambda b: tuple(b))
    class Reducer:
        mean = staticmethod(lambda: "mean")
    ImageCollection = staticmethod(lambda name: Coll())


STATE = {"reject_geographic": False, "other_error": False, "log": []}


def tif(arr, tr):
    with MemoryFile() as mf:
        with mf.open(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype="float32", crs="EPSG:4326", transform=tr) as d:
            d.write(arr[None].astype("float32"))
        return mf.read()


class R:
    def __init__(self, c): self.content = c
    def raise_for_status(self): pass


def main() -> None:
    try:
        Coll().median().reduceResolution(reducer="mean", maxPixels=1024)
        raise SystemExit("GAGAL: tiruan harus menolak urutan lama")
    except EEException:
        pass
    m.requests.get = lambda url, timeout: R(tif(np.full((300, 300), 0.2), from_origin(103.5, -1.0, 0.00225, 0.00225)))
    args = (FakeEE, (103.5, -1.7, 104.3, -1.0), date(2018, 12, 1), date(2018, 12, 31), 250.0)
    assert m.fetch_ndmi_tile(*args)
    ops = STATE["log"][-1]
    assert ops.index("setDefaultProjection") < ops.index("reduceResolution") < ops.index("reproject") and "unmask" in ops
    STATE.update(reject_geographic=True, log=[])
    assert m.fetch_ndmi_tile(*args) and len(STATE["log"]) == 1
    STATE.update(reject_geographic=False, other_error=True)
    try:
        m.fetch_ndmi_tile(*args)
        raise SystemExit("GAGAL: galat lain harus diteruskan")
    except EEException as e:
        assert "timed out" in str(e)
    x0, _ = to_grid(103.9, -1.3)
    _, y0 = to_grid(103.9, -1.3)
    cx0, cy_top = int(x0 // 1000), int(y0 // 1000) + 3
    uni = {"shape": (6, 8), "cx0": cx0, "cy_top": cy_top, "valid": np.ones((6, 8), bool), "static": {}}
    lon_c, lat_c = cell_grid_lonlat(uni)
    w, n, px = lon_c.min() - 0.05, lat_c.max() + 0.05, 0.00225
    W, H = int((lon_c.max() + 0.05 - w) / px), int((n - (lat_c.min() - 0.05)) / px)
    lo = w + (np.arange(W) + 0.5) * px
    arr = np.where(lo[None, :] < lon_c[:, :4].max() + 0.001, -9999.0, 0.25) * np.ones((H, 1))
    tab = m.ndmi_to_cells([tif(arr, from_origin(w, n, px, px))], uni, date(2024, 1, 1), date(2024, 1, 31))
    assert (tab.ndmi > 0.2).all() and (tab.cx >= cx0 + 3).all() and len(tab) < 48
    print("test_02f_ndmi: LOLOS (urutan proyeksi, cadangan, galat lain, NODATA)")


if __name__ == "__main__":
    main()
