"""RF-22: exportar precios procesados, resultados por activo, tabla
comparativa y parámetros — con fecha y fuente."""
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from io import StringIO

import pandas as pd

from src.comparison import ComparisonRow
from src.data import PriceSeries


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def export_prices_csv(price_series_map: dict[str, PriceSeries]) -> str:
    """Precios procesados (limpios/remuestreados) de todos los activos,
    en formato largo: fecha, ticker, precio, moneda, fuente."""
    frames = []
    for ticker, ps in price_series_map.items():
        df = ps.prices.rename("adjusted_close").reset_index()
        df.columns = ["date", "adjusted_close"]
        df["ticker"] = ticker
        df["currency"] = ps.currency
        df["source"] = ps.source
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    combined = combined[["date", "ticker", "adjusted_close", "currency", "source"]]
    buffer = StringIO()
    combined.to_csv(buffer, index=False)
    return buffer.getvalue()


def export_comparison_table_csv(rows: list[ComparisonRow]) -> str:
    """RF-19/RF-22: tabla comparativa (coordenadas del mapa + RVR)."""
    df = pd.DataFrame(
        [
            {
                "ticker": r.ticker,
                "vol_annual": r.vol_annual,
                "mean_annual": r.mean_annual,
                "rvr": r.rvr,
                "n_obs_common": r.n_obs_common,
            }
            for r in rows
        ]
    )
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue()


def export_full_bundle_json(
    price_series_map: dict[str, PriceSeries],
    comparison_rows: list[ComparisonRow],
    parameters: dict,
    fetch_errors: dict[str, str] | None = None,
) -> str:
    """Exportación completa en un solo JSON: precios, tabla comparativa
    y parámetros usados — con fecha y fuente (RF-22)."""
    payload = {
        "exported_at": _timestamp(),
        "parameters": _json_safe(parameters),
        "sources": {ticker: ps.source for ticker, ps in price_series_map.items()},
        "errors": fetch_errors or {},
        "prices": {
            ticker: {
                "dates": [d.isoformat() for d in ps.prices.index],
                "adjusted_close": ps.prices.tolist(),
                "currency": ps.currency,
                "timezone": ps.timezone,
                "price_adjusted": ps.price_adjusted,
            }
            for ticker, ps in price_series_map.items()
        },
        "comparison_table": [
            {
                "ticker": r.ticker,
                "vol_annual": r.vol_annual,
                "mean_annual": r.mean_annual,
                "rvr": r.rvr,
                "n_obs_common": r.n_obs_common,
            }
            for r in comparison_rows
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _json_safe(value):
    """Convierte tipos no serializables comunes (date, dataclasses,
    Timestamps de pandas, etc.) a algo que json.dumps acepte."""
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (date, pd.Timestamp)):
        return value.isoformat()
    return value


# --- Exportación por activo individual (VaR, niveles, forecasting) ---------

def export_asset_analysis_json(
    ticker: str,
    price_series: PriceSeries,
    present_context,
    descriptive,
    trajectories: dict[str, list],
    var_results: dict,
    signals: dict,
) -> str:
    """RF-22: 'resultados por activo' — VaR, niveles de entrada/salida,
    probabilidades y trayectoria de forecasting, por cada modelo
    calculado para este ticker. Con fecha y fuente."""
    payload = {
        "exported_at": _timestamp(),
        "ticker": ticker,
        "source": price_series.source,
        "currency": price_series.currency,
        "price_adjusted": price_series.price_adjusted,
        "present_context": _json_safe(present_context),
        "descriptive_stats": _json_safe(descriptive),
        "forecast_trajectories": {
            model: _json_safe(steps) for model, steps in trajectories.items()
        },
        "var": {model: _json_safe(v) for model, v in var_results.items()},
        "signals": {model: _json_safe(s) for model, s in signals.items()},
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def export_asset_analysis_csv(
    ticker: str,
    var_results: dict,
    signals: dict,
) -> str:
    """Resumen plano (una fila por modelo) de VaR y niveles de decisión
    para este activo — complemento tabular al JSON completo."""
    rows = []
    for model in var_results:
        var_r = var_results[model]
        sig = signals.get(model)
        rows.append(
            {
                "ticker": ticker,
                "modelo": model,
                "var_confianza": var_r.confidence,
                "var_horizonte": var_r.horizon,
                "var_fraccion": var_r.fraction,
                "var_monetario": var_r.monetary,
                "entrada": sig.entry if sig else None,
                "stop_loss": sig.sl_h if sig else None,
                "take_profit": sig.tp_h if sig else None,
                "precio_equilibrio": sig.p_be if sig else None,
                "br_neto": sig.br_neto if sig else None,
                "prob_ganar": sig.prob_win if sig else None,
                "prob_perder": sig.prob_loss if sig else None,
                "hay_senal": sig.has_signal if sig else None,
                "condiciones_fallidas": (
                    "; ".join(sig.failed_conditions) if sig and sig.failed_conditions else ""
                ),
            }
        )
    buffer = StringIO()
    pd.DataFrame(rows).to_csv(buffer, index=False)
    return buffer.getvalue()
