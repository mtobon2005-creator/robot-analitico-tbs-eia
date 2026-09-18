"""RF-05 a RF-08: descarga, limpieza, remuestreo y calidad de datos.

Orden obligatorio (RF-07): remuestrear PRIMERO, calcular rendimientos
DESPUÉS. Este módulo solo produce series de PRECIOS ya limpias y
remuestreadas; el cálculo de rendimientos logarítmicos es RF-09/RF-10
(módulo futuro) y debe operar siempre sobre la salida de aquí.
"""
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol

import pandas as pd

MIN_OBSERVATIONS_BY_FREQUENCY = {
    "Diaria": 30,
    "Semanal": 12,
    "Mensual": 6,
}  # RF-08: umbral mínimo para considerar la muestra utilizable. Escala
# por frecuencia porque 30 observaciones significa ~6 semanas en
# diaria, pero ¡2.5 años! en mensual — un mínimo único no tiene
# sentido entre frecuencias tan distintas. (La validación walk-forward
# de RF-15 tiene su propio umbral, mucho más estricto y correcto para
# ese propósito: n_min = max(2m, 5H); este umbral aquí solo evita
# muestras degeneradas, ej. 2-3 observaciones.)
MIN_OBSERVATIONS = MIN_OBSERVATIONS_BY_FREQUENCY["Diaria"]  # compatibilidad hacia atrás


class TickerNotFound(Exception):
    pass


class EmptyResponse(Exception):
    pass


class ProviderTimeout(Exception):
    pass


class InsufficientSample(Exception):
    pass


@dataclass
class RawPriceResponse:
    ticker: str
    dates: list
    prices: list
    currency: str
    timezone: str
    source: str
    price_adjusted: bool = True


class PriceProvider(Protocol):
    def fetch(self, ticker: str, start: date, end: date) -> RawPriceResponse: ...


# --- RF-05: proveedores -----------------------------------------------------

class FixtureProvider:
    """Proveedor sin internet (PROVIDER-01: 'No internet dependency').
    Lee el fixture sintético oficial del curso — no redistribuye datos
    de mercado reales."""

    def __init__(self, csv_path: Path):
        self._df = pd.read_csv(csv_path, parse_dates=["date"])

    def fetch(self, ticker: str, start: date, end: date) -> RawPriceResponse:
        subset = self._df[self._df["ticker"] == ticker]
        if subset.empty:
            raise TickerNotFound(f"Ticker '{ticker}' no existe en la fuente.")

        subset = subset[
            (subset["date"] >= pd.Timestamp(start)) & (subset["date"] <= pd.Timestamp(end))
        ]
        if subset.empty:
            raise EmptyResponse(
                f"Sin datos para '{ticker}' en el rango {start} a {end}."
            )

        row0 = subset.iloc[0]
        return RawPriceResponse(
            ticker=ticker,
            dates=list(subset["date"]),
            prices=list(subset["adjusted_close"]),
            currency=row0["currency"],
            timezone=row0["timezone"],
            source=row0["source"],
            price_adjusted=True,
        )


class MockProvider:
    """Proveedor configurable para pruebas (PROVIDER-01): simula cada
    caso — 'valid', 'empty', 'timeout', 'nonpositive', 'ticker_missing'
    — sin depender de internet."""

    def __init__(self, behaviors: dict[str, str]):
        self._behaviors = behaviors

    def fetch(self, ticker: str, start: date, end: date) -> RawPriceResponse:
        behavior = self._behaviors.get(ticker, "ticker_missing")

        if behavior == "ticker_missing":
            raise TickerNotFound(f"Ticker '{ticker}' no existe.")
        if behavior == "empty":
            raise EmptyResponse(f"Respuesta vacía para '{ticker}'.")
        if behavior == "timeout":
            raise ProviderTimeout(f"Timeout al consultar '{ticker}'.")
        if behavior == "nonpositive":
            return RawPriceResponse(
                ticker=ticker,
                dates=pd.date_range(start, periods=35, freq="D"),
                prices=[100.0] * 34 + [-5.0],  # una observación inválida al final
                currency="USD",
                timezone="America/New_York",
                source="mock",
            )
        if behavior == "valid":
            return RawPriceResponse(
                ticker=ticker,
                dates=pd.date_range(start, periods=35, freq="D"),
                prices=[100.0 + i * 0.1 for i in range(35)],
                currency="USD",
                timezone="America/New_York",
                source="mock",
            )
        raise ValueError(f"Comportamiento mock desconocido: '{behavior}'.")


class YFinanceProvider:
    """Proveedor real (Yahoo Finance vía librería yfinance). Requiere
    internet — NO se usa en las pruebas automatizadas (PROVIDER-01
    exige cero dependencia de internet en tests). Instalar con:
    pip install yfinance

    LIMITACIÓN CONOCIDA: yfinance no expone la zona horaria del
    exchange de forma trivial en todas sus versiones; aquí se reporta
    'UTC' como aproximación y debe verificarse manualmente contra la
    fuente real antes de usar en el piloto final (RF-05 exige mostrar
    zona horaria real)."""

    def fetch(self, ticker: str, start: date, end: date) -> RawPriceResponse:
        import yfinance as yf

        try:
            data = yf.download(
                ticker, start=start, end=end, progress=False, auto_adjust=True
            )
        except Exception as exc:  # noqa: BLE001 — cualquier fallo de red se trata como timeout
            raise ProviderTimeout(str(exc)) from exc

        if data is None or data.empty:
            raise EmptyResponse(f"Respuesta vacía de yfinance para '{ticker}'.")

        close = data["Close"]
        if hasattr(close, "columns"):  # MultiIndex en versiones recientes
            close = close.iloc[:, 0]

        return RawPriceResponse(
            ticker=ticker,
            dates=list(close.index.date),
            prices=list(close.values),
            currency="USD",  # TODO: confirmar con yf.Ticker(ticker).fast_info.currency
            timezone="UTC",  # ver limitación en el docstring de la clase
            source="Yahoo Finance (yfinance)",
            price_adjusted=True,
        )


# --- RF-06: limpieza --------------------------------------------------------

def clean_prices(raw: RawPriceResponse) -> tuple[pd.Series, dict]:
    """Ordena fechas, elimina duplicados, descarta faltantes y precios
    no positivos — todo reportado explícitamente (nada se pierde en
    silencio)."""
    df = pd.DataFrame({"date": pd.to_datetime(raw.dates), "price": raw.prices})
    n_total = len(df)

    df = df.sort_values("date")

    n0 = len(df)
    df = df.drop_duplicates(subset="date", keep="last")
    dropped_duplicates = n0 - len(df)

    n0 = len(df)
    df = df.dropna(subset=["price"])
    dropped_missing = n0 - len(df)

    n0 = len(df)
    df = df[df["price"] > 0]
    dropped_nonpositive = n0 - len(df)

    series = df.set_index("date")["price"].astype(float)
    report = {
        "n_total_received": n_total,
        "dropped_duplicates": dropped_duplicates,
        "dropped_missing": dropped_missing,
        "dropped_nonpositive": dropped_nonpositive,
        "n_final": len(series),
    }
    return series, report


# --- RF-07: remuestreo -------------------------------------------------------

_RESAMPLE_RULE = {"Diaria": None, "Semanal": "W-FRI", "Mensual": "ME"}


def resample_prices(series: pd.Series, frequency: str) -> pd.Series:
    """Remuestrear ANTES de calcular rendimientos (RF-07). 'Diaria' no
    se remuestrea (es la granularidad base recibida). 'Semanal' usa
    W-FRI (semana termina el viernes) y 'Mensual' usa fin de mes — el
    último precio válido del periodo, verificado contra RESAMPLE-01
    (109 precios semanales / 26 mensuales para AAPL en el fixture
    oficial)."""
    rule = _RESAMPLE_RULE.get(frequency)
    if rule is None:
        return series
    return series.resample(rule).last().dropna()


# --- RF-08: validación de calidad y orquestación multi-ticker ----------------

def validate_sufficient_sample(series: pd.Series, minimum: int = MIN_OBSERVATIONS) -> None:
    if len(series) < minimum:
        raise InsufficientSample(
            f"Muestra insuficiente: {len(series)} observaciones "
            f"(mínimo {minimum})."
        )


@dataclass
class PriceSeries:
    ticker: str
    prices: pd.Series
    currency: str
    timezone: str
    source: str
    price_adjusted: bool
    cleaning_report: dict


@dataclass
class FetchResult:
    ok: dict[str, PriceSeries] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


def fetch_and_clean_many(
    tickers: list[str],
    provider: PriceProvider,
    start: date,
    end: date,
    frequency: str,
    min_observations: int | None = None,
) -> FetchResult:
    """RF-08: cada ticker se valida de forma INDEPENDIENTE. Un fallo en
    uno no detiene ni elimina los resultados válidos de los demás
    (T-06 / FAIL-20P1-01: 20 válidos + 1 inválido conservan los 20).

    `min_observations=None` (el caso normal) usa el umbral propio de
    la `frequency` elegida (MIN_OBSERVATIONS_BY_FREQUENCY) — pasar un
    valor explícito lo sobreescribe (útil en pruebas)."""
    if min_observations is None:
        min_observations = MIN_OBSERVATIONS_BY_FREQUENCY.get(frequency, MIN_OBSERVATIONS)

    result = FetchResult()
    for ticker in tickers:
        try:
            raw = provider.fetch(ticker, start, end)
            series, report = clean_prices(raw)
            series = resample_prices(series, frequency)
            validate_sufficient_sample(series, min_observations)
        except (TickerNotFound, EmptyResponse, ProviderTimeout, InsufficientSample) as exc:
            result.errors[ticker] = f"{type(exc).__name__}: {exc}"
            continue

        result.ok[ticker] = PriceSeries(
            ticker=ticker,
            prices=series,
            currency=raw.currency,
            timezone=raw.timezone,
            source=raw.source,
            price_adjusted=raw.price_adjusted,
            cleaning_report=report,
        )
    return result
