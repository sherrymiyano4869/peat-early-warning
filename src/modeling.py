"""Konstanta dan pembantu model yang dipakai bersama oleh 04_baseline dan 06_predict."""
from lightgbm import LGBMRegressor

RAIN_COLS = ["rain_7d", "rain_14d", "rain_30d", "dry_days", "dry_max_30d", "rain_days_30d"]
SAT_ABS = ["vv", "vh", "ndmi"]
SAT_ANOM = ["vv_anom", "vh_anom", "ndmi_anom"]
ENSO_COLS = ["nino34", "dmi"]
STATIC_COLS = ["elev_m", "slope_deg", "fabdem_elev_m", "fabdem_slope_deg", "fabdem_relief_500m", "fabdem_relief_1km",
               "canal_density_500m", "canal_density_1km"]
TREND_COLS = ["wl_d3", "wl_d7"]
LGB = dict(n_estimators=200, learning_rate=0.05, num_leaves=15, min_child_samples=30, subsample=0.8,
           subsample_freq=1, colsample_bytree=0.8, random_state=0, verbose=-1, n_jobs=1)


def make_lgbm(alpha=None):
    return LGBMRegressor(objective="quantile", alpha=alpha, **LGB) if alpha else LGBMRegressor(**LGB)


def feature_sets(df, no_static=False, abs_sat=False, with_enso=False):
    """Kolom fitur yang tersedia di df: (hujan, satelit, statis, tren, enso)."""
    rain = [c for c in RAIN_COLS if c in df]
    sat = [c for c in SAT_ANOM if c in df] or [c for c in SAT_ABS if c in df]
    if abs_sat:
        sat += [c for c in SAT_ABS if c in df and c not in sat]
    static = [] if no_static else [c for c in STATIC_COLS if c in df]
    trend = [c for c in TREND_COLS if c in df]
    enso = [c for c in ENSO_COLS if c in df] if with_enso else []
    return rain, sat, static, trend, enso
