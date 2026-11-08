"""Cek bahwa lingkungan 'peat' lengkap: impor semua pustaka dan cetak versinya.

    python scripts/check_env.py
"""
import importlib
import sys

PACKAGES = [
    "numpy", "pandas", "scipy", "pyarrow", "yaml", "requests", "openpyxl",
    "ee", "geopandas", "shapely", "pyproj", "pyogrio", "rasterio", "xarray",
    "rioxarray", "netCDF4", "pysheds", "sklearn", "lightgbm", "xgboost",
    "statsmodels", "shap", "joblib", "optuna", "mapie", "properscoring",
    "matplotlib", "seaborn", "plotly", "folium", "streamlit", "streamlit_folium",
]


def main() -> None:
    print(f"Python {sys.version.split()[0]}")
    gagal = []
    for name in PACKAGES:
        try:
            mod = importlib.import_module(name)
            print(f"  ok   {name:<17} {getattr(mod, '__version__', '-')}")
        except Exception as err:  # noqa: BLE001
            print(f"  GAGAL {name:<16} {err}")
            gagal.append(name)
    if gagal:
        sys.exit(f"\nTidak lengkap: {', '.join(gagal)}")
    print("\nSemua pustaka terpasang.")


if __name__ == "__main__":
    main()
