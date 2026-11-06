"""Botiverso — punto de entrada y navegación.

Robot analítico de preselección de activos y portafolios — proyecto de
Teoría Moderna de Portafolios, Tech Business School / Universidad EIA.
"""
import json

import streamlit as st
import altair as alt
import numpy as np
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

from src import auth, sessions, audit
from src.black_litterman import BlackLittermanError, black_litterman
from src.covariance import correlation_from_covariance, shrink_to_diagonal
from src.portfolio import (
    PortfolioOptimizationError,
    efficient_frontier,
    global_min_variance,
    max_expected_return,
    personal_optimum,
    portfolio_log_returns,
    portfolio_simple_returns,
    portfolio_var,
    tangency_portfolio,
)
from src.beta_capm import (
    BetaCapmError,
    beta_covariance,
    beta_ols,
    capm_ke,
    convert_ke_by_inflation,
    relever_beta,
    unlever_beta,
)
from src.rebalance import RebalanceError, rebalance
from src.technical import rank_by_momentum
from src.traceability import build_trace_record
from src.valuation import (
    ValuationError,
    present_value,
    project_years,
    terminal_value_gordon,
    wacc,
)
from src.performance import (
    PerformanceError,
    capital_market_line,
    information_ratio,
    jensens_alpha,
    systematic_risk_share,
    treynor_ratio,
)
from src.fx import FxError, convert_price_series
from src.config import APP_IDENTITY, FRECUENCIAS, MAX_HORIZON_PERIODS, N_MIN_ACTIVOS
from src.consent import PreconsentInvalid, issue_preconsent_flow
from src.db import get_connection, init_schema
from src.disclaimer import (
    DISCLAIMER_TEXT,
    DISCLAIMER_VERSION,
    EXECUTION_POLICY_SECTIONS,
    EXECUTION_POLICY_VERSION,
)
from src.analytics import (
    build_present_context,
    compare_full_vs_recent_window,
    compute_drawdown_series,
    compute_log_returns,
    descriptive_stats,
    max_drawdown,
    quantile_type7,
)
from src.comparison import (
    IncompatibleCurrencies,
    InsufficientAssetsForComparison,
    build_comparison_table,
    compute_non_dominated,
    select_max_mean_under_risk_limit,
    select_max_rvr,
    select_min_volatility_under_mean_floor,
    select_non_dominated_set,
)
from src.data import FetchResult, FixtureProvider, fetch_and_clean_many
from src.export import (
    export_asset_analysis_csv,
    export_asset_analysis_json,
    export_comparison_table_csv,
    export_full_bundle_json,
    export_prices_csv,
)
from src.forecasting import (
    InsufficientWalkForwardSample,
    estimate_train_params,
    generate_trajectory,
    horizon_params,
    validate_walk_forward,
)
from src.risk import (
    DEFAULT_BR_MIN,
    DEFAULT_C_B,
    DEFAULT_C_S,
    DEFAULT_P_L,
    DEFAULT_P_U,
    InvalidCostRate,
    InvalidTailProbabilities,
    compute_var,
    evaluate_signal,
)
from src.horizon import (
    InvalidDateRange,
    InvalidFrequency,
    InvalidHorizon,
    resolve_horizon,
    validate_date_range,
)
from src.privacy import PRIVACY_NOTICE_TEXT, PRIVACY_NOTICE_VERSION
from src.tickers import (
    TickerNotFound,
    add_tickers_bulk,
    is_ready_for_comparison,
    is_ready_for_single_asset,
    missing_for_comparison,
    remove_ticker,
)

# Los mismos 20 tickers del fixture sintético del curso (RF-05), para
# poder probar comparación/portafolio sin escribirlos uno por uno.
_FIXTURE_TICKERS_PRESET = [
    "AAPL", "AMZN", "CAT", "COST", "GOOGL", "HD", "JNJ", "JPM", "KO", "MA",
    "MCD", "META", "MSFT", "NVDA", "PEP", "PG", "UNH", "V", "WMT", "XOM",
]

# Universo ampliado de 50 large caps reales (superset del anterior, más
# variedad de sectores) — solo tiene datos en el fixture sintético para
# los 20 de arriba; los 30 adicionales requieren Yahoo Finance real.
_EXTENDED_TICKERS_PRESET = _FIXTURE_TICKERS_PRESET + [
    "BAC", "WFC", "GS", "MS", "AXP", "BRK-B", "DIS", "NKE", "SBUX", "TSLA",
    "ORCL", "ADBE", "CRM", "INTC", "CSCO", "AMD", "QCOM", "IBM", "PFE", "MRK",
    "ABBV", "LLY", "TMO", "ABT", "CVX", "BA", "GE", "HON", "UPS", "VZ",
]

# Para probar la conversión de moneda (src/fx.py): dos activos en USD
# + cuatro activos de la Bolsa de Valores de Colombia, todos
# confirmados en COP por la estudiante en finance.yahoo.com (requiere
# Yahoo Finance real, no están en el fixture sintético): ISA
# (Interconexión Eléctrica S.A. E.S.P.), Ecopetrol S.A., y Grupo
# Cibest S.A. (ordinaria y preferencial).
_FX_DEMO_TICKERS_PRESET = [
    "AAPL", "MSFT", "ISA.CL", "ECOPETROL.CL", "CIBEST.CL", "PFCIBEST.CL",
]

_LOGO_PATH = Path(__file__).parent / "assets" / "logo_botiverso.svg"
_LOGO_SVG = _LOGO_PATH.read_text(encoding="utf-8") if _LOGO_PATH.exists() else None

st.set_page_config(
    page_title=APP_IDENTITY.system_name,
    page_icon=str(_LOGO_PATH) if _LOGO_SVG else "📊",
    layout="wide",
)


@st.cache_resource
def _get_shared_connection():
    conn = get_connection()
    init_schema(conn)
    return conn


def _render_identity_header() -> None:
    if _LOGO_SVG:
        # st.image maneja SVG de forma nativa y confiable (a diferencia
        # de incrustarlo crudo con st.markdown+unsafe_allow_html, que
        # dejaba de mostrar el ícono porque el <svg> sin width/height
        # propio cae al tamaño por defecto del navegador dentro de un
        # <div> sin ancho forzado). El SVG trae su propio <title>/<desc>
        # con role="img" aria-labelledby; un <h1> visualmente oculto
        # mantiene la estructura de encabezado para lectores de pantalla
        # sin duplicar visualmente el nombre que ya trae el logo.
        st.markdown(
            "<span style='position:absolute;width:1px;height:1px;padding:0;"
            "margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:"
            f"nowrap;border:0'><h1>{APP_IDENTITY.system_name}</h1></span>",
            unsafe_allow_html=True,
        )
        st.image(str(_LOGO_PATH), width=380)
    else:
        col_avatar, col_text = st.columns([1, 5])
        with col_avatar:
            st.markdown(
                f"<div role='img' aria-label='{APP_IDENTITY.avatar_alt_text}' "
                f"style='font-size:48px'>📊</div>",
                unsafe_allow_html=True,
            )
        with col_text:
            st.title(APP_IDENTITY.system_name)
    st.caption(
        f"Versión {APP_IDENTITY.version} · Actualizado "
        f"{APP_IDENTITY.updated_at} · Equipo: {APP_IDENTITY.team_name}"
    )


def _render_execution_policy() -> None:
    with st.expander("Política de ejecución (contrato lógico del sistema)"):
        st.caption(f"Versión {EXECUTION_POLICY_VERSION}")
        for section_title, section_text in EXECUTION_POLICY_SECTIONS.items():
            st.markdown(f"**{section_title}.** {section_text}")


def _render_access_gate(conn) -> None:
    """Vista pública: identidad, disclaimer, privacidad, botones OIDC.

    Dos controles SEPARADOS y NO premarcados (sección 3.3): privacidad
    y disclaimer. Solo al aceptar ambos se habilita el login OIDC.
    """
    st.header("Disclaimer académico")
    st.info(DISCLAIMER_TEXT)
    st.caption(f"Versión del disclaimer: {DISCLAIMER_VERSION}")
    disclaimer_ok = st.checkbox(
        "He leído y acepto el disclaimer académico.", key="cb_disclaimer"
    )

    st.header("Aviso de privacidad")
    st.info(PRIVACY_NOTICE_TEXT)
    st.caption(f"Versión del aviso de privacidad: {PRIVACY_NOTICE_VERSION}")
    privacy_ok = st.checkbox(
        "He leído y autorizo el tratamiento de datos descrito arriba.",
        key="cb_privacy",
    )

    both_accepted = disclaimer_ok and privacy_ok
    if not both_accepted:
        st.warning("Debes aceptar ambos controles para continuar.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "Continuar con Google", disabled=not both_accepted, use_container_width=True
        ):
            _start_login(conn, provider="google")
    with col2:
        if st.button(
            "Continuar con Microsoft", disabled=not both_accepted, use_container_width=True
        ):
            _start_login(conn, provider="microsoft")


def _start_login(conn, provider: str) -> None:
    """Redirige al proveedor OIDC elegido.

    Ya NO emite el preconsent_flow aquí (ver docstring de
    _finalize_login_if_needed): ni session_state ni una cookie propia
    sobreviven de forma confiable el redirect completo en todos los
    entornos de hosting. La confirmación real de disclaimer/privacidad
    ocurre justo después de volver autenticado."""
    st.login(provider=provider)


def _finalize_login_if_needed(conn) -> None:
    """Se ejecuta justo después del callback OIDC: st.user.is_logged_in
    es True pero todavía no tenemos session_id local -> completar login."""
    if st.session_state.get("session_id"):
        return  # ya finalizado en un rerun anterior

    claims = dict(st.user)

    # Si ya existe una sesión activa para esta identidad (ej. el
    # navegador recargó la página estando ya autenticado — Streamlit
    # pierde session_state en cualquier recarga completa, no solo en
    # el redirect OIDC), la retomamos en vez de exigir login de nuevo.
    existing = auth.find_active_session_for_claims(conn, claims)
    if existing:
        st.session_state["session_id"] = existing["session_id"]
        st.session_state["user_id"] = existing["user_id"]
        return

    # Confirmación de consentimiento DESPUÉS del login, no antes del
    # redirect. Motivo (limitación descubierta y documentada): ni
    # st.session_state ni una cookie propia sobreviven de forma
    # confiable el viaje completo a Google/Microsoft y de vuelta en
    # todos los entornos de hosting (confirmado en Streamlit Community
    # Cloud, donde el iframe usado para la cookie corre aislado en
    # otro origen). Pedir la confirmación aquí, en un rerun normal
    # posterior al callback, es 100% fiable porque ya no cruza ningún
    # redirect — session_state funciona con normalidad de aquí en
    # adelante para el resto de la sesión.
    if not st.session_state.get("post_login_consent_given"):
        st.info(f"Hola, {claims.get('name', 'usuario')} — confirma antes de continuar:")
        st.info(DISCLAIMER_TEXT)
        st.caption(f"Versión del disclaimer: {DISCLAIMER_VERSION}")
        d_ok = st.checkbox(
            "He leído y acepto el disclaimer académico.", key="cb_disclaimer_post"
        )
        st.info(PRIVACY_NOTICE_TEXT)
        st.caption(f"Versión del aviso de privacidad: {PRIVACY_NOTICE_VERSION}")
        p_ok = st.checkbox(
            "He leído y autorizo el tratamiento de datos descrito arriba.",
            key="cb_privacy_post",
        )
        if st.button("Confirmar y continuar", disabled=not (d_ok and p_ok)):
            st.session_state["post_login_consent_given"] = True
            st.rerun()
        return

    iss = claims.get("iss", "")
    provider = "microsoft" if "microsoftonline" in iss else "google"
    # Se emite y se consume el flow en la MISMA ejecución (nunca cruza
    # un redirect), por lo que siempre es válido en este punto.
    flow_id = issue_preconsent_flow(
        conn, disclaimer_version=DISCLAIMER_VERSION, privacy_version=PRIVACY_NOTICE_VERSION
    )

    try:
        result = auth.complete_login(conn, claims, provider, flow_id)
    except PreconsentInvalid:
        st.error(
            "El preconsentimiento expiró, ya fue usado o no existe. "
            "Cierra sesión y vuelve a aceptar el disclaimer y el aviso "
            "de privacidad antes de reintentar."
        )
        st.button("Cerrar sesión y reintentar", on_click=st.logout)
        st.stop()
    except auth.IdentityIncomplete:
        st.error(
            "Tu cuenta no tiene nombre o correo verificado disponible "
            "(identity_incomplete). No es posible continuar."
        )
        st.button("Cerrar sesión", on_click=st.logout)
        st.stop()
    except auth.NotAuthorized:
        st.error("Esta cuenta no está autorizada para el piloto (allowlist).")
        st.button("Cerrar sesión", on_click=st.logout)
        st.stop()
    else:
        st.session_state["session_id"] = result["session_id"]
        st.session_state["user_id"] = result["user_id"]
        st.rerun()


def _guard(conn) -> bool:
    """Verifica TTL de la sesión lógica en cada rerun protegido.
    Devuelve True si la sesión sigue activa."""
    session_id = st.session_state.get("session_id")
    if not session_id:
        return False
    try:
        sessions.touch_session(conn, session_id)
        return True
    except sessions.SessionExpired:
        audit.record_auth_event(
            conn,
            user_id=st.session_state.get("user_id", "unknown"),
            session_id=session_id,
            event_type="expired",
            result="success",
            app_version=APP_IDENTITY.version,
        )
        for key in ("session_id", "user_id"):
            st.session_state.pop(key, None)
        st.warning("Tu sesión expiró por inactividad o por superar 8 horas. Vuelve a iniciar sesión.")
        st.button("Ir al acceso", on_click=st.logout)
        return False
    except sessions.SessionNotFound:
        st.session_state.pop("session_id", None)
        return False


def _render_ticker_collection() -> list[str]:
    """RF-03: colección dinámica de tickers. Devuelve la colección
    actual (lista de strings normalizados)."""
    st.header("Selección de activos")
    collection: list[str] = st.session_state.setdefault("ticker_collection", [])

    with st.form(key="add_ticker_form", clear_on_submit=True):
        raw_tickers = st.text_area(
            "Agregar ticker(s)",
            placeholder=(
                "Uno o varios, separados por coma, espacio o salto de línea.\n"
                "Ej: AAPL, MSFT, BRK.B\no pega una lista completa de una vez."
            ),
            height=80,
            label_visibility="collapsed",
            key="raw_tickers_input",
        )
        submitted = st.form_submit_button("Agregar", use_container_width=True)

    if submitted and raw_tickers.strip():
        new_collection, errors = add_tickers_bulk(collection, raw_tickers)
        st.session_state["ticker_collection"] = new_collection
        st.session_state["ticker_bulk_errors"] = errors
        st.rerun()

    bulk_errors = st.session_state.pop("ticker_bulk_errors", None)
    if bulk_errors:
        with st.expander(f"⚠️ {len(bulk_errors)} ticker(s) no se agregaron", expanded=True):
            for raw, reason in bulk_errors:
                st.write(f"- **{raw}**: {reason}")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Cargar universo de prueba (20 activos del fixture sintético)"):
            new_collection, _ = add_tickers_bulk(collection, " ".join(_FIXTURE_TICKERS_PRESET))
            st.session_state["ticker_collection"] = new_collection
            st.rerun()
    with col2:
        if st.button("Cargar universo ampliado (50 — requiere Yahoo Finance real)"):
            new_collection, _ = add_tickers_bulk(collection, " ".join(_EXTENDED_TICKERS_PRESET))
            st.session_state["ticker_collection"] = new_collection
            st.rerun()
    with col3:
        if st.button("Probar conversión de moneda (AAPL, MSFT (USD) + 4 activos BVC en COP)"):
            new_collection, _ = add_tickers_bulk(collection, " ".join(_FX_DEMO_TICKERS_PRESET))
            st.session_state["ticker_collection"] = new_collection
            st.rerun()
    st.caption(
        "El universo ampliado solo tiene precios en el fixture sintético "
        "para los primeros 20 — los 30 adicionales, y el preset de "
        "conversión de moneda, necesitan 'Yahoo Finance (datos reales)' "
        "como fuente abajo."
    )

    if collection:
        st.write(f"**{len(set(collection))} activo(s) en la colección:**")
        # Chips con botón de eliminar individual.
        n_cols = 5
        rows = [collection[i : i + n_cols] for i in range(0, len(collection), n_cols)]
        for row in rows:
            cols = st.columns(n_cols)
            for col, ticker in zip(cols, row):
                with col:
                    if st.button(f"✕ {ticker}", key=f"remove_{ticker}"):
                        try:
                            st.session_state["ticker_collection"] = remove_ticker(
                                collection, ticker
                            )
                        except TickerNotFound:
                            pass
                        st.rerun()
    else:
        st.caption("Aún no has agregado ningún ticker.")

    if is_ready_for_single_asset(collection):
        st.success("Modo: análisis de un solo activo. Listo para continuar.")
    elif is_ready_for_comparison(collection):
        st.success(
            f"Modo: comparación de {len(set(collection))} activos válidos "
            f"(mínimo {N_MIN_ACTIVOS} cumplido)."
        )
    elif len(collection) > 1:
        faltan = missing_for_comparison(collection)
        st.info(
            f"Tienes {len(set(collection))} activo(s). Para comparación "
            f"necesitas {N_MIN_ACTIVOS} — faltan {faltan}. Para análisis "
            "individual, deja solo 1 activo en la colección."
        )
    else:
        st.info(
            f"Agrega 1 activo (análisis individual) o al menos "
            f"{N_MIN_ACTIVOS} (comparación)."
        )

    return collection


def _render_date_frequency_horizon() -> None:
    """RF-04: fechas, frecuencia y horizonte H (libre, no solo botones)."""
    st.header("Fechas, frecuencia y horizonte")

    col1, col2, col3 = st.columns(3)
    with col1:
        fecha_inicial = st.date_input(
            "Fecha inicial", value=date.today() - timedelta(days=365), key="fecha_inicial"
        )
    with col2:
        fecha_final = st.date_input("Fecha final", value=date.today(), key="fecha_final")
    with col3:
        frecuencia = st.selectbox("Frecuencia", options=list(FRECUENCIAS.keys()), key="frecuencia")

    try:
        validate_date_range(fecha_inicial, fecha_final)
    except InvalidDateRange as exc:
        st.error(str(exc))
        return

    st.caption(
        f"Ventana: {fecha_inicial.isoformat()} → {fecha_final.isoformat()} · "
        f"{FRECUENCIAS[frecuencia]} periodos/año en frecuencia {frecuencia.lower()}."
    )

    st.markdown("**Horizonte de pronóstico H**")
    modo = st.radio(
        "¿Cómo quieres definir H?",
        options=["Cantidad de periodos", "Fecha objetivo"],
        horizontal=True,
        key="horizon_mode_radio",
    )

    horizon_config = None
    if modo == "Cantidad de periodos":
        h_input = st.number_input(
            f"H (entero, periodos {frecuencia.lower()}s; máx. "
            f"{MAX_HORIZON_PERIODS} — puedes escribir cualquier valor, no "
            "solo los botones sugeridos)",
            min_value=1,
            step=1,
            value=17,
            key="horizon_periods_input",
        )
        try:
            horizon_config = resolve_horizon(
                frecuencia, fecha_final, mode="periods", periods=int(h_input)
            )
        except InvalidHorizon as exc:
            st.error(str(exc))
    else:
        target = st.date_input(
            "Fecha objetivo (posterior a la fecha final)",
            value=fecha_final + timedelta(days=30),
            key="horizon_target_date_input",
        )
        try:
            horizon_config = resolve_horizon(
                frecuencia, fecha_final, mode="target_date", target_date=target
            )
        except (InvalidHorizon, InvalidFrequency) as exc:
            st.error(str(exc))

    if horizon_config:
        st.success(
            f"H resuelto = {horizon_config.periods} periodo(s) "
            f"{frecuencia.lower()}(s)."
            + (
                f" (equivalente aproximado a la fecha objetivo "
                f"{horizon_config.target_date.isoformat()} — se recalculará "
                "contra el calendario real de datos en RF-14)."
                if horizon_config.mode == "target_date"
                else ""
            )
        )
        st.session_state["date_config"] = {
            "fecha_inicial": fecha_inicial,
            "fecha_final": fecha_final,
            "frecuencia": frecuencia,
        }
        st.session_state["horizon_config"] = horizon_config


_FIXTURE_CSV_PATH = (
    Path(__file__).resolve().parent / "tests" / "fixtures" / "Fixture_20_activos_sintetico_TBS_EIA.csv"
)


@st.cache_resource
def _get_fixture_provider() -> FixtureProvider:
    return FixtureProvider(_FIXTURE_CSV_PATH)


@st.cache_resource
def _get_yfinance_provider():
    from src.data import YFinanceProvider

    return YFinanceProvider()


def _render_data_fetch(collection: list[str]) -> None:
    """RF-05 a RF-08: descarga (fixture o Yahoo Finance, a elección),
    limpieza, remuestreo y aislamiento de fallos parciales."""
    st.header("Descarga y calidad de datos")

    date_config = st.session_state.get("date_config")
    horizon_config = st.session_state.get("horizon_config")
    if not date_config or not horizon_config:
        st.info("Completa fechas/frecuencia/horizonte arriba antes de descargar.")
        return
    if not collection:
        st.info("Agrega al menos un ticker arriba antes de descargar.")
        return

    fuente = st.radio(
        "Fuente de datos",
        options=["Fixture de prueba (sin internet)", "Yahoo Finance (datos reales)"],
        horizontal=True,
        key="data_source_choice",
    )
    if fuente.startswith("Fixture"):
        st.caption(
            "Proveedor activo: **fixture sintético del curso** — "
            "TBS-EIA-SYNTH, no son datos de mercado reales."
        )
    else:
        st.caption(
            "Proveedor activo: **Yahoo Finance (yfinance)** — datos "
            "reales, requiere internet y `pip install yfinance`. Zona "
            "horaria/moneda reportadas son aproximadas (ver limitación "
            "en `src/data.py::YFinanceProvider`)."
        )

    if st.button("Descargar y limpiar datos"):
        provider = (
            _get_fixture_provider()
            if fuente.startswith("Fixture")
            else _get_yfinance_provider()
        )
        result: FetchResult = fetch_and_clean_many(
            tickers=collection,
            provider=provider,
            start=date_config["fecha_inicial"],
            end=date_config["fecha_final"],
            frequency=date_config["frecuencia"],
        )
        st.session_state["fetch_result"] = result

    result = st.session_state.get("fetch_result")
    if result is None:
        return

    if result.ok:
        st.success(f"{len(result.ok)} activo(s) válido(s).")
        rows = [
            {
                "Ticker": ticker,
                "Observaciones": len(ps.prices),
                "Último precio": round(ps.prices.iloc[-1], 4),
                "Moneda": ps.currency,
                "Zona horaria": ps.timezone,
                "Fuente": ps.source,
                "Ajustado": "Sí" if ps.price_adjusted else "No",
                "Descartados (dup/faltante/no-positivo)": (
                    f"{ps.cleaning_report['dropped_duplicates']}/"
                    f"{ps.cleaning_report['dropped_missing']}/"
                    f"{ps.cleaning_report['dropped_nonpositive']}"
                ),
            }
            for ticker, ps in result.ok.items()
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

    if result.errors:
        st.warning(
            f"{len(result.errors)} activo(s) con error — el análisis de "
            "los demás NO se detiene (RF-08)."
        )
        for ticker, message in result.errors.items():
            st.write(f"- **{ticker}**: {message}")


def _render_historical_analysis() -> None:
    """RF-09 a RF-12: gráficos, rendimientos logarítmicos, descriptivos
    y contexto del presente (drawdown, percentil, ventana reciente)."""
    st.header("Análisis histórico")

    result: FetchResult | None = st.session_state.get("fetch_result")
    date_config = st.session_state.get("date_config")
    if not result or not result.ok or not date_config:
        st.info("Descarga datos válidos arriba para ver el análisis histórico.")
        return

    ticker = st.selectbox(
        "Activo a analizar en detalle", options=sorted(result.ok.keys()), key="analysis_ticker"
    )
    price_series = result.ok[ticker]
    prices = price_series.prices
    returns = compute_log_returns(prices)
    frequency = date_config["frecuencia"]

    # RF-09: gráficos con título, ticker, unidad, frecuencia, fechas y fuente.
    caption = (
        f"{ticker} · {price_series.currency} · frecuencia {frequency.lower()} · "
        f"{prices.index[0].date()} a {prices.index[-1].date()} · "
        f"fuente: {price_series.source}"
    )
    st.markdown(f"**Precio vs. tiempo — {ticker}**")
    st.caption(caption)
    st.line_chart(prices, use_container_width=True)
    with st.expander("Ver datos de precio en tabla (alternativa accesible al gráfico)"):
        st.dataframe(
            prices.rename("Precio").reset_index().rename(columns={"index": "Fecha"}),
            use_container_width=True, hide_index=True,
        )

    st.markdown(f"**Log-rendimiento vs. tiempo — {ticker}**")
    st.caption(caption)
    st.line_chart(returns, use_container_width=True)
    with st.expander("Ver datos de rendimiento en tabla (alternativa accesible al gráfico)"):
        st.dataframe(
            returns.rename("Log-rendimiento").reset_index().rename(columns={"index": "Fecha"}),
            use_container_width=True, hide_index=True,
        )

    # RF-10: ecuación única de rendimiento (nunca simple).
    st.caption(f"Ecuación de rendimiento (única admitida): g_t = ln(Pₜ / Pₜ₋₁)")

    # RF-12: contexto del presente.
    ctx = build_present_context(prices, returns)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Último precio", f"{ctx.last_price:.4f}", help=str(ctx.last_date.date()))
    col2.metric("Último log-rendimiento", f"{ctx.last_log_return:.6f}")
    col3.metric("Drawdown actual", f"{ctx.drawdown_now:.2%}")
    col4.metric("Máxima caída histórica", f"{ctx.max_drawdown_value:.2%}")
    st.caption(
        f"Percentil (midrank) del último rendimiento dentro de la muestra: "
        f"{ctx.last_return_percentile:.1f}%"
    )

    with st.expander("Serie de drawdown completa"):
        drawdown_series = compute_drawdown_series(prices)
        st.line_chart(drawdown_series, use_container_width=True)
        with st.expander("Ver drawdown en tabla (alternativa accesible al gráfico)"):
            st.dataframe(
                drawdown_series.rename("Drawdown").reset_index().rename(columns={"index": "Fecha"}),
                use_container_width=True, hide_index=True,
            )

    # RF-11: estadísticas descriptivas (periodo y anualizadas).
    stats_ = descriptive_stats(returns, frequency)
    q05 = quantile_type7(returns, 5)
    q95 = quantile_type7(returns, 95)

    st.markdown("**Estadísticas descriptivas**")
    stat_rows = [
        {"Métrica": "N observaciones", "Valor": stats_.n_obs},
        {"Métrica": "Media (periodo)", "Valor": f"{stats_.mean_period:.6f}"},
        {"Métrica": "Mediana (periodo)", "Valor": f"{stats_.median_period:.6f}"},
        {"Métrica": "Desv. estándar (periodo)", "Valor": f"{stats_.sd_period:.6f}"},
        {"Métrica": "Percentil 5% (tipo 7)", "Valor": f"{q05:.6f}"},
        {"Métrica": "Percentil 95% (tipo 7)", "Valor": f"{q95:.6f}"},
        {"Métrica": "Asimetría (Fisher, corregida)", "Valor": f"{stats_.skewness:.4f}"},
        {"Métrica": "Exceso de curtosis (Fisher, corregida)", "Valor": f"{stats_.excess_kurtosis:.4f}"},
        {"Métrica": "Media anualizada (estimador)", "Valor": f"{stats_.mean_annual:.4%}"},
        {"Métrica": "Volatilidad anualizada", "Valor": f"{stats_.sd_annual:.4%}"},
        {
            "Métrica": "RVR (media/vol. anualizada)",
            "Valor": f"{stats_.rvr:.4f}" if stats_.rvr is not None else "Indefinida (vol=0)",
        },
    ]
    st.dataframe(stat_rows, use_container_width=True, hide_index=True)
    st.caption(
        "La media anualizada es un **estimador histórico**, no una promesa de "
        "rendimiento futuro (sección 5, guía de la actividad)."
    )

    # Comparación muestra completa vs. ventana reciente (RF-12).
    comparison = compare_full_vs_recent_window(returns, frequency)
    label = "parcial (T < m)" if comparison.is_partial else "completa"
    with st.expander(
        f"Ventana reciente (últimas {comparison.recent_window_size} obs., {label}) "
        "vs. muestra completa"
    ):
        st.write(
            f"- Volatilidad anualizada, muestra completa: "
            f"{comparison.full_sample.sd_annual:.4%}\n"
            f"- Volatilidad anualizada, ventana reciente: "
            f"{comparison.recent_window.sd_annual:.4%}"
        )


def _render_forecasting() -> None:
    """RF-13 a RF-15: forecasting homocedástico multihorizonte y
    validación walk-forward."""
    st.header("Forecasting homocedástico")

    result: FetchResult | None = st.session_state.get("fetch_result")
    date_config = st.session_state.get("date_config")
    horizon_config = st.session_state.get("horizon_config")
    if not result or not result.ok or not date_config or not horizon_config:
        st.info(
            "Descarga datos y configura el horizonte H arriba antes de "
            "ver el forecasting."
        )
        return

    ticker = st.session_state.get("analysis_ticker") or sorted(result.ok.keys())[0]
    st.caption(f"Activo: **{ticker}** · H = {horizon_config.periods} periodos")

    prices = result.ok[ticker].prices
    returns = compute_log_returns(prices)
    params = estimate_train_params(returns)  # todo el historial disponible

    modelos = st.multiselect(
        "Modelo(s) homocedástico(s)",
        options=["A", "B"],
        default=["A", "B"],
        format_func=lambda m: "A — caminata aleatoria sin deriva" if m == "A"
        else "B — lognormal con deriva",
        key="forecast_models",
    )
    if not modelos:
        st.warning("Selecciona al menos un modelo.")
        return

    st.caption(
        f"Parámetros estimados con TODO el historial disponible: "
        f"μ̂={params.mu_train:.6f}, σ̂={params.sigma_train:.6f} (por periodo, "
        "sin anualizar). La validación walk-forward de abajo sí reestima "
        "estos parámetros usando solo datos disponibles en cada origen."
    )

    p_t = float(prices.iloc[-1])
    for modelo in modelos:
        trajectory = generate_trajectory(p_t, params, modelo, horizon_config.periods)
        nombre = "A (caminata aleatoria)" if modelo == "A" else "B (lognormal con deriva)"
        st.markdown(f"**Modelo {nombre} — trayectoria 1 a H={horizon_config.periods}**")

        chart_df = pd.DataFrame(
            {
                "h": [s.h for s in trajectory],
                "Mediana": [s.median for s in trajectory],
                "Media": [s.mean for s in trajectory],
                "Q05": [s.q05 for s in trajectory],
                "Q95": [s.q95 for s in trajectory],
            }
        ).set_index("h")
        st.line_chart(chart_df, use_container_width=True)
        with st.expander(
            f"Ver trayectoria del Modelo {modelo} en tabla (alternativa accesible al gráfico)"
        ):
            st.dataframe(chart_df.reset_index(), use_container_width=True, hide_index=True)

        terminal = trajectory[-1]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Mediana terminal", f"{terminal.median:.4f}")
        col2.metric("Media terminal", f"{terminal.mean:.4f}")
        col3.metric("Q05 terminal", f"{terminal.q05:.4f}")
        col4.metric("Q95 terminal", f"{terminal.q95:.4f}")

        with st.expander(f"Validación walk-forward — Modelo {modelo}"):
            frequency = date_config["frecuencia"]
            m = FRECUENCIAS[frequency]
            try:
                wf = validate_walk_forward(
                    prices, returns, modelo, horizon_config.periods, m
                )
            except InsufficientWalkForwardSample as exc:
                st.warning(f"**No señal** — {exc}")
                continue

            st.write(
                f"- Orígenes evaluados: {wf.origins}\n"
                f"- MAE (logespacio): {wf.mae:.6f}\n"
                f"- RMSE (logespacio): {wf.rmse:.6f}\n"
                f"- Cobertura del intervalo central 90%: {wf.coverage:.1%}\n"
                + (
                    f"- Exactitud direccional: {wf.direction_accuracy:.1%} "
                    f"(sobre {wf.direction_n} orígenes calificados)"
                    if wf.direction_accuracy is not None
                    else "- Exactitud direccional: N/A (m_h = 0 en todos los orígenes)"
                )
            )


def _render_risk_and_levels() -> None:
    """RF-16 a RF-18: VaR paramétrico, niveles de entrada/SL/TP y
    probabilidades terminales para la posición larga obligatoria."""
    st.header("Riesgo, niveles de decisión y probabilidades")

    result: FetchResult | None = st.session_state.get("fetch_result")
    date_config = st.session_state.get("date_config")
    horizon_config = st.session_state.get("horizon_config")
    modelos = st.session_state.get("forecast_models") or []
    if not result or not result.ok or not date_config or not horizon_config or not modelos:
        st.info("Completa forecasting arriba (con al menos un modelo) antes de ver esta sección.")
        return

    ticker = st.session_state.get("analysis_ticker") or sorted(result.ok.keys())[0]
    prices = result.ok[ticker].prices
    returns = compute_log_returns(prices)
    params = estimate_train_params(returns)
    p_t = float(prices.iloc[-1])

    col1, col2, col3 = st.columns(3)
    with col1:
        confidence = st.selectbox("Confianza del VaR", options=[0.95, 0.99], key="var_confidence")
        capital = st.number_input(
            "Capital hipotético", min_value=1.0, value=10000.0, step=1000.0, key="var_capital"
        )
    with col2:
        p_l = st.number_input(
            "p_L (cola inferior, SL)", min_value=0.001, max_value=0.499, value=DEFAULT_P_L,
            step=0.01, key="risk_p_l",
        )
        p_u = st.number_input(
            "p_U (cola superior, TP)", min_value=0.501, max_value=0.999, value=DEFAULT_P_U,
            step=0.01, key="risk_p_u",
        )
    with col3:
        c_b = st.number_input(
            "Costo de compra c_b", min_value=0.0, value=DEFAULT_C_B, step=0.001,
            format="%.4f", key="risk_c_b",
        )
        c_s = st.number_input(
            "Costo de venta c_s", min_value=0.0, max_value=0.999, value=DEFAULT_C_S,
            step=0.001, format="%.4f", key="risk_c_s",
        )
        br_min = st.number_input(
            "BR mínimo exigido", min_value=0.0, value=DEFAULT_BR_MIN, step=0.1, key="risk_br_min"
        )

    export_var_results: dict = {}
    export_signals: dict = {}
    export_trajectories: dict = {}

    for modelo in modelos:
        nombre = "A (caminata aleatoria)" if modelo == "A" else "B (lognormal con deriva)"
        st.markdown(f"**Modelo {nombre}**")
        dist = horizon_params(modelo, params, horizon_config.periods)

        var_result = compute_var(dist, confidence, capital)
        col1, col2 = st.columns(2)
        col1.metric(f"VaR {int(confidence*100)}% (fracción)", f"{var_result.fraction:.4%}")
        col2.metric(f"VaR {int(confidence*100)}% (monetario)", f"{var_result.monetary:,.2f}")
        st.caption(
            "El VaR no es la pérdida máxima posible ni informa la magnitud "
            "media de la pérdida más allá del cuantil; puede subestimar el "
            "riesgo si hay colas gruesas (puntos 36-38 de la guía)."
        )

        try:
            signal = evaluate_signal(
                p_t, dist, p_l=p_l, p_u=p_u, br_min=br_min, c_b=c_b, c_s=c_s
            )
        except (InvalidTailProbabilities, InvalidCostRate) as exc:
            st.error(str(exc))
            continue

        export_var_results[modelo] = var_result
        export_signals[modelo] = signal
        export_trajectories[modelo] = generate_trajectory(
            p_t, params, modelo, horizon_config.periods
        )

        level_rows = [
            {"Nivel": "Entrada (E)", "Valor": f"{signal.entry:.4f}"},
            {"Nivel": "Stop-loss (SL_H)", "Valor": f"{signal.sl_h:.4f}"},
            {"Nivel": "Take-profit (TP_H)", "Valor": f"{signal.tp_h:.4f}"},
            {"Nivel": "Precio de equilibrio (P_BE)", "Valor": f"{signal.p_be:.4f}"},
            {"Nivel": "Riesgo neto (D_neto)", "Valor": f"{signal.d_neto:.4f}"},
            {"Nivel": "Beneficio neto (U_neto)", "Valor": f"{signal.u_neto:.4f}"},
            {
                "Nivel": "BR neto",
                "Valor": f"{signal.br_neto:.4f}" if signal.br_neto is not None else "No calculable",
            },
            {"Nivel": "Prob. terminal de ganar", "Valor": f"{signal.prob_win:.2%}"},
            {"Nivel": "Prob. terminal de perder", "Valor": f"{signal.prob_loss:.2%}"},
            {"Nivel": "Prob. terminal neutral", "Valor": f"{signal.prob_neutral:.2%}"},
        ]
        st.dataframe(level_rows, use_container_width=True, hide_index=True)

        if signal.has_signal:
            st.success("**Señal**: se cumplen todas las condiciones reproducibles de 5.7.")
        else:
            st.warning(
                "**No señal** — condición(es) que fallaron: "
                + "; ".join(signal.failed_conditions)
            )
        st.caption(
            "Esto es una herramienta académica de preselección — no "
            "constituye recomendación de inversión ni garantía de resultado."
        )

    if export_var_results:
        st.markdown("**Exportar resultados de este activo (RF-22)**")
        price_series = result.ok[ticker]
        present_context = build_present_context(prices, returns)
        descriptive = descriptive_stats(returns, date_config["frecuencia"])

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                f"Resultados {ticker} — resumen (CSV)",
                data=export_asset_analysis_csv(ticker, export_var_results, export_signals),
                file_name=f"resultados_{ticker}.csv",
                mime="text/csv",
            )
        with col2:
            st.download_button(
                f"Resultados {ticker} — completo (JSON)",
                data=export_asset_analysis_json(
                    ticker, price_series, present_context, descriptive,
                    export_trajectories, export_var_results, export_signals,
                ),
                file_name=f"resultados_{ticker}.json",
                mime="application/json",
            )


def _render_comparison_and_export() -> None:
    """RF-19 a RF-22: mapa histórico rendimiento-riesgo, dominancia,
    regla de preselección y exportación."""
    st.header("Comparación de activos y exportación")

    result: FetchResult | None = st.session_state.get("fetch_result")
    date_config = st.session_state.get("date_config")
    if not result or not result.ok or not date_config:
        st.info("Descarga datos válidos arriba antes de comparar.")
        return

    frequency = date_config["frecuencia"]

    try:
        rows = build_comparison_table(result.ok, frequency)
    except InsufficientAssetsForComparison as exc:
        st.info(str(exc))
        return
    except IncompatibleCurrencies as exc:
        st.error(str(exc))
        return

    non_dominated = compute_non_dominated(rows)
    map_df = pd.DataFrame(
        [
            {
                "ticker": r.ticker,
                "vol_annual": r.vol_annual,
                "mean_annual": r.mean_annual,
                "rvr": r.rvr if r.rvr is not None else float("nan"),
                "no_dominado": r.ticker in non_dominated,
            }
            for r in rows
        ]
    )

    st.caption(
        f"Mapa histórico — {len(rows)} activos válidos · frecuencia "
        f"{frequency.lower()} · fechas comunes intersectadas · moneda "
        f"base única. Las coordenadas NO cambian con H."
    )

    points = (
        alt.Chart(map_df)
        .mark_circle(size=120)
        .encode(
            x=alt.X("vol_annual", title="Volatilidad anualizada"),
            y=alt.Y("mean_annual", title="Media histórica logarítmica anualizada"),
            color=alt.Color("no_dominado", title="No dominado"),
            tooltip=["ticker", "vol_annual", "mean_annual", "rvr"],
        )
    )
    labels = (
        alt.Chart(map_df)
        .mark_text(dy=-12, fontSize=11)
        .encode(x="vol_annual", y="mean_annual", text="ticker")
    )
    st.altair_chart(points + labels, use_container_width=True)
    st.caption(
        "Nota: este mapa compara activos INDIVIDUALES — no calcula pesos, "
        "covarianzas ni frontera eficiente de portafolios (RF-19/RF-20)."
    )

    with st.expander("Tabla comparativa completa"):
        st.dataframe(map_df, use_container_width=True, hide_index=True)

    st.markdown("**Regla de preselección**")
    regla = st.radio(
        "Criterio",
        options=[
            "Máxima media bajo límite de riesgo",
            "Mínima volatilidad bajo media mínima",
            "Máxima razón media-volatilidad (RVR)",
            "Conjunto no dominado",
        ],
        key="selection_rule",
    )

    if regla == "Máxima media bajo límite de riesgo":
        limite = st.number_input("Límite de riesgo (volatilidad anualizada)", value=0.30, step=0.01)
        selection = select_max_mean_under_risk_limit(rows, limite)
    elif regla == "Mínima volatilidad bajo media mínima":
        piso = st.number_input("Media mínima exigida (anualizada)", value=0.05, step=0.01)
        selection = select_min_volatility_under_mean_floor(rows, piso)
    elif regla == "Máxima razón media-volatilidad (RVR)":
        selection = select_max_rvr(rows)
    else:
        selection = select_non_dominated_set(rows)

    if selection.selected_tickers:
        st.success(
            f"**Mejor según el criterio elegido:** {', '.join(selection.selected_tickers)}"
        )
    else:
        st.warning("Ningún activo cumple el criterio con los parámetros indicados.")
    st.caption(
        "Esta selección refleja el criterio y los parámetros elegidos — "
        "NO es una frontera eficiente ni implica que exista una 'mejor "
        "inversión universal' (RF-21)."
    )

    st.markdown("**Exportar (RF-22)**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Precios procesados (CSV)",
            data=export_prices_csv(result.ok),
            file_name="precios_procesados.csv",
            mime="text/csv",
        )
    with col2:
        st.download_button(
            "Tabla comparativa (CSV)",
            data=export_comparison_table_csv(rows),
            file_name="tabla_comparativa.csv",
            mime="text/csv",
        )
    with col3:
        horizon_cfg = st.session_state.get("horizon_config")
        horizon_dict = (
            {
                "mode": horizon_cfg.mode,
                "frequency": horizon_cfg.frequency,
                "periods": horizon_cfg.periods,
                "target_date": horizon_cfg.target_date,
            }
            if horizon_cfg
            else {}
        )
        bundle = export_full_bundle_json(
            result.ok,
            rows,
            parameters={**date_config, "horizon": horizon_dict},
            fetch_errors=result.errors,
        )
        st.download_button(
            "Todo (JSON)", data=bundle, file_name="export_completo.json", mime="application/json"
        )


def _render_portfolio_v2(result: FetchResult | None, date_config: dict | None) -> dict | None:
    """Mandato v2 (ver README, sección "Mandato v2"): Markowitz N
    activos, Black-Litterman y rebalanceo simulado sobre los activos ya
    descargados arriba. No sustituye el núcleo v1 (RF-01 a RF-22)."""
    st.header("Portafolio v2: Markowitz, Black-Litterman y rebalanceo")

    if not result or not result.ok or not date_config:
        st.info("Descarga datos válidos arriba antes de optimizar un portafolio.")
        return
    if len(result.ok) < 2:
        st.info("Necesitas al menos 2 activos válidos para optimizar un portafolio.")
        return

    tickers = sorted(result.ok.keys())
    selected = st.multiselect(
        "Activos a incluir en el portafolio", options=tickers, default=tickers,
        key="portfolio_assets",
    )
    if len(selected) < 2:
        st.warning("Selecciona al menos 2 activos.")
        return

    currencies = {result.ok[t].currency for t in selected}
    base_currency = next(iter(currencies))
    fx_rates: dict[str, float] = {}
    if len(currencies) > 1:
        st.warning(
            f"Los activos seleccionados tienen monedas distintas ({', '.join(sorted(currencies))}). "
            "Convierte todo a una moneda base con una tasa de cambio "
            "(GUIA_V2 §3.2, P_base=P_original*FX) antes de optimizar."
        )
        base_currency = st.selectbox(
            "Moneda base del portafolio", options=sorted(currencies), key="portfolio_fx_base"
        )
        otras_monedas = sorted(c for c in currencies if c != base_currency)
        fx_error = False
        for moneda in otras_monedas:
            rate = st.number_input(
                f"Tasa de cambio: 1 {moneda} = ? {base_currency}", min_value=0.0,
                value=4000.0 if {moneda, base_currency} == {"USD", "COP"} else 1.0,
                step=0.01, format="%.4f", key=f"portfolio_fx_rate_{moneda}",
            )
            if rate <= 0:
                st.error(f"La tasa para {moneda} debe ser positiva.")
                fx_error = True
            fx_rates[moneda] = rate
        if fx_error:
            return
        st.caption(
            "Con una tasa constante (un solo número, no una serie histórica "
            "de FX), la conversión NO cambia los pesos óptimos de Markowitz "
            "— los retornos porcentuales son invariantes a multiplicar toda "
            "la serie de precios por una constante. Sí permite analizar los "
            "activos juntos y expresar montos (VaR, rebalanceo, ficha "
            "técnica) en una sola moneda. No modela el riesgo cambiario "
            "(la volatilidad de la tasa de cambio en sí)."
        )

    price_series_by_ticker = {}
    for t in selected:
        prices_t = result.ok[t].prices
        moneda_t = result.ok[t].currency
        if moneda_t != base_currency:
            try:
                prices_t = convert_price_series(prices_t, fx_rates[moneda_t])
            except FxError as exc:
                st.error(f"{t}: {exc}")
                return
        price_series_by_ticker[t] = prices_t
    price_df = pd.DataFrame(price_series_by_ticker)
    simple_returns = price_df.pct_change(fill_method=None)
    common_mask = simple_returns.notna().all(axis=1)
    simple_returns = simple_returns.loc[common_mask]
    n_obs = len(simple_returns)
    n_assets = len(selected)
    frequency = date_config["frecuencia"]
    m = FRECUENCIAS[frequency]
    # Con T observaciones y N activos, Sigma (NxN) es singular si T<=N y
    # queda mal condicionada si T no es varias veces N (GUIA_V2, P37/P38:
    # "qué cambia cuando N se aproxima a T"). Exigir un mínimo proporcional
    # a N evita un Sigma casi singular que solo pasaría un umbral fijo.
    # Cualquier frecuencia sirve — Mensual solo necesita un rango de
    # fechas más amplio para juntar las mismas observaciones que Diaria
    # junta en pocos meses.
    min_obs_required = max(30, 3 * n_assets)
    if n_obs < min_obs_required:
        years_needed = min_obs_required / m
        st.warning(
            f"Solo {n_obs} observaciones comunes tras alinear fechas para "
            f"{n_assets} activos — se necesitan al menos {min_obs_required} "
            "(≈3× el número de activos) para que Σ no quede casi singular "
            f"(GUIA_V2, P37/P38). Con frecuencia **{frequency.lower()}** "
            f"({m} periodos/año) eso equivale a un rango de al menos "
            f"**{years_needed:.1f} años** — amplía 'Fecha inicial' arriba "
            "(o cambia a una frecuencia más densa) y vuelve a descargar."
        )
        return
    mu_annual = simple_returns.mean().to_numpy() * m
    Sigma_annual = simple_returns.cov(ddof=1).to_numpy() * m

    st.caption(
        f"{n_obs} observaciones comunes en {frequency.lower()} · retornos simples "
        "(agregación de cartera, GUIA_V2 §4.1), anualizados linealmente (μ×m, Σ×m)."
    )
    with st.expander("Ver μ y Σ anualizados"):
        sigma_cols = {f"Σ {t}": Sigma_annual[:, i] for i, t in enumerate(selected)}
        st.dataframe(
            pd.DataFrame({"Activo": selected, "μ anual": mu_annual}).assign(**sigma_cols),
            use_container_width=True, hide_index=True,
        )

    st.markdown("**Matriz de correlación**")
    corr_matrix = correlation_from_covariance(Sigma_annual)
    corr_long = pd.DataFrame(
        [
            {"Activo A": selected[i], "Activo B": selected[j], "Correlación": corr_matrix[i, j]}
            for i in range(n_assets)
            for j in range(n_assets)
        ]
    )
    heatmap = alt.Chart(corr_long).mark_rect().encode(
        x=alt.X("Activo A:O", title=None),
        y=alt.Y("Activo B:O", title=None),
        color=alt.Color(
            "Correlación:Q", scale=alt.Scale(scheme="redblue", domain=[-1, 1], reverse=True)
        ),
        tooltip=["Activo A", "Activo B", alt.Tooltip("Correlación:Q", format=".4f")],
    )
    text = alt.Chart(corr_long).mark_text(fontSize=10).encode(
        x="Activo A:O", y="Activo B:O", text=alt.Text("Correlación:Q", format=".2f"),
        color=alt.condition(
            "abs(datum.Correlación) > 0.6", alt.value("white"), alt.value("black")
        ),
    )
    st.altair_chart(heatmap + text, use_container_width=True)
    with st.expander("Ver matriz de correlación en tabla (alternativa accesible al mapa de calor)"):
        corr_df = pd.DataFrame(corr_matrix, index=selected, columns=selected)
        st.dataframe(corr_df, use_container_width=True)
    st.caption(
        "rho_ij = Sigma_ij / (sigma_i x sigma_j), derivada de la misma Σ "
        "anualizada usada en la optimización de arriba — coherente con "
        "las carteras calculadas, no un cálculo aparte."
    )

    col1, col2 = st.columns(2)
    with col1:
        rf_anual = st.number_input(
            "Tasa libre de riesgo (efectiva anual)", min_value=0.0, max_value=1.0,
            value=0.03, step=0.005, format="%.4f", key="portfolio_rf",
        )
    with col2:
        gamma = st.number_input(
            "Gamma (aversión al riesgo del inversionista)", min_value=0.01,
            value=5.0, step=0.5, key="portfolio_gamma",
        )
    bounds = [(0.0, 1.0)] * len(selected)

    usar_shrinkage = st.checkbox(
        "Comparar con covarianza shrinkage hacia la diagonal (GUIA_V2, P39)",
        key="portfolio_use_shrinkage",
    )
    Sigma_shrunk = None
    if usar_shrinkage:
        shrink_delta = st.slider(
            "delta (0 = Σ muestral sin cambios; 1 = activos tratados como "
            "independientes)",
            min_value=0.0, max_value=1.0, value=0.2, step=0.05,
            key="portfolio_shrink_delta",
        )
        shrink_result = shrink_to_diagonal(Sigma_annual, shrink_delta)
        Sigma_shrunk = shrink_result.Sigma
        st.caption(
            "La covarianza muestral con pocas observaciones relativas a N "
            "activos sobreajusta la frontera (Sharpe irrealmente altos, "
            "carteras muy concentradas). Elegiste delta tú — no se ajustó "
            "mirando el resultado (P39)."
        )

    try:
        gmv = global_min_variance(mu_annual, Sigma_annual, bounds=bounds)
        tan = tangency_portfolio(mu_annual, Sigma_annual, rf_anual, bounds=bounds)
        opt = personal_optimum(mu_annual, Sigma_annual, gamma, bounds=bounds)
        maxret = max_expected_return(mu_annual, Sigma_annual, bounds=bounds)
    except PortfolioOptimizationError as exc:
        st.error(f"El solver de portafolio no convergió: {exc}")
        return

    st.markdown("**Carteras clave**")
    carteras_rows = []
    for nombre, res in [
        ("Mínima varianza (GMV)", gmv),
        ("Tangente (máx. Sharpe)", tan),
        (f"Óptimo personal (γ={gamma:g})", opt),
        ("Máximo retorno esperado", maxret),
    ]:
        row = {"Cartera": nombre, "μ anual": f"{res.expected_return:.4%}", "σ anual": f"{res.volatility:.4%}"}
        row.update({t: f"{w:.2%}" for t, w in zip(selected, res.weights)})
        carteras_rows.append(row)

    if Sigma_shrunk is not None:
        try:
            gmv_s = global_min_variance(mu_annual, Sigma_shrunk, bounds=bounds)
            tan_s = tangency_portfolio(mu_annual, Sigma_shrunk, rf_anual, bounds=bounds)
            opt_s = personal_optimum(mu_annual, Sigma_shrunk, gamma, bounds=bounds)
        except PortfolioOptimizationError as exc:
            st.error(f"El solver no convergió con Σ shrinkage: {exc}")
        else:
            for nombre, res in [
                (f"Mínima varianza — shrinkage δ={shrink_delta:g}", gmv_s),
                (f"Tangente — shrinkage δ={shrink_delta:g}", tan_s),
                (f"Óptimo personal (γ={gamma:g}) — shrinkage δ={shrink_delta:g}", opt_s),
            ]:
                row = {
                    "Cartera": nombre,
                    "μ anual": f"{res.expected_return:.4%}",
                    "σ anual": f"{res.volatility:.4%}",
                }
                row.update({t: f"{w:.2%}" for t, w in zip(selected, res.weights)})
                carteras_rows.append(row)

    st.dataframe(carteras_rows, use_container_width=True, hide_index=True)
    st.caption(
        "GMV depende solo de Σ, no de μ (GUIA_V2, tabla 5.1). El óptimo "
        "personal requiere γ del inversionista — no se infiere de los "
        "precios históricos (P57). Compara cuánto se concentran los pesos "
        "'crudos' contra su versión con shrinkage: menos concentración y "
        "un Sharpe más realista en la tangente suele indicar que la "
        "versión cruda estaba sobreajustada al ruido de la muestra."
    )

    st.markdown("**Frontera eficiente**")
    targets = np.linspace(gmv.expected_return, maxret.expected_return, 12)
    frontier_results, infeasible = efficient_frontier(mu_annual, Sigma_annual, targets, bounds=bounds)
    if infeasible:
        st.caption(f"{len(infeasible)} punto(s) objetivo inviable(s) bajo las cotas [0,1] por activo.")
    if frontier_results:
        frontier_df = pd.DataFrame(
            {
                "sigma": [r.volatility for r in frontier_results],
                "mu": [r.expected_return for r in frontier_results],
            }
        )
        points_df = pd.DataFrame(
            {
                "sigma": [gmv.volatility, tan.volatility, opt.volatility, maxret.volatility],
                "mu": [gmv.expected_return, tan.expected_return, opt.expected_return, maxret.expected_return],
                "cartera": ["GMV", "Tangente", "Óptimo personal", "Máx. retorno"],
            }
        )
        line = alt.Chart(frontier_df).mark_line(point=True).encode(
            x=alt.X("sigma", title="Volatilidad anualizada"),
            y=alt.Y("mu", title="Retorno esperado anualizado"),
        )
        markers = alt.Chart(points_df).mark_point(size=150, filled=True, color="red").encode(
            x="sigma", y="mu", tooltip=["cartera", "sigma", "mu"]
        )
        labels = alt.Chart(points_df).mark_text(dy=-12, fontSize=11).encode(x="sigma", y="mu", text="cartera")

        sigma_max_cml = max(float(frontier_df["sigma"].max()), tan.volatility) * 1.3
        cml_sigma = np.linspace(0.0, sigma_max_cml, 25)
        cml_mu = capital_market_line(rf_anual, tan.expected_return, tan.volatility, cml_sigma)
        cml_df = pd.DataFrame({"sigma": cml_sigma, "mu": cml_mu})
        cml_line = alt.Chart(cml_df).mark_line(strokeDash=[6, 3], color="green").encode(x="sigma", y="mu")

        st.altair_chart(line + cml_line + markers + labels, use_container_width=True)
        st.caption(
            "Línea verde punteada: Línea del Mercado de Capitales (CML), "
            "combinaciones de activo libre de riesgo + cartera tangente — "
            "pendiente = Sharpe de la tangente. Para sigma > sigma_tangente "
            "implica apalancarse a rf (tomar prestado) para invertir más "
            "que el 100% en la tangente; este bot no ejecuta eso, es solo "
            "la referencia teórica."
        )
        with st.expander("Ver puntos de la frontera en tabla (alternativa accesible al gráfico)"):
            st.dataframe(frontier_df, use_container_width=True, hide_index=True)
    else:
        st.caption("Ningún punto de la frontera fue factible con las cotas actuales.")

    st.markdown("**Black-Litterman (opcional)**")
    usar_bl = st.checkbox(
        "Actualizar μ con Black-Litterman antes de re-optimizar", key="portfolio_use_bl"
    )
    bl_tan_weights = None
    if usar_bl:
        st.caption(
            "w_ref por defecto es equiponderado — no hay capitalización de "
            "mercado real disponible aquí (P66/P71). Sin una view, el "
            "posterior conserva el prior tal cual (P2-19)."
        )
        n = len(selected)
        col1, col2 = st.columns(2)
        with col1:
            delta = st.number_input(
                "delta (aversión implícita del prior)", min_value=0.01, value=2.5,
                step=0.1, key="bl_delta",
            )
        with col2:
            tau = st.number_input(
                "tau", min_value=0.001, value=0.05, step=0.01, format="%.3f", key="bl_tau"
            )
        w_ref = np.full(n, 1.0 / n)

        with st.expander("Ver momentum de tus activos (ayuda para elegir una view)"):
            st.caption(
                "Momentum = retorno acumulado en los últimos N días. Es una "
                "señal, no una tesis — la tesis (por qué crees que va a "
                "continuar) sigue siendo tuya (P129)."
            )
            momentum_window = st.slider(
                "Ventana (días)", min_value=5, max_value=120, value=20, step=5,
                key="momentum_window",
            )
            momentum_ranking = rank_by_momentum(
                {t: result.ok[t].prices for t in selected}, momentum_window
            )
            if momentum_ranking:
                st.dataframe(
                    [
                        {"Activo": r.ticker, f"Momentum {r.window}d": f"{r.momentum:+.2%}", "N precios": r.n_obs}
                        for r in momentum_ranking
                    ],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("Ningún activo tiene suficiente historia para esta ventana.")

        agregar_view = st.checkbox("Agregar una view absoluta propia", key="bl_add_view")
        P_view = Q_view = Omega_view = None
        if agregar_view:
            col1, col2, col3 = st.columns(3)
            with col1:
                activo_view = st.selectbox("Activo", options=selected, key="bl_view_asset")
            with col2:
                idx = selected.index(activo_view)
                retorno_view = st.number_input(
                    "Tu retorno anual esperado (tesis propia)",
                    value=float(mu_annual[idx]), step=0.01, format="%.4f", key="bl_view_return",
                )
            with col3:
                confianza_view = st.slider(
                    "Confianza (%)", min_value=1, max_value=99, value=50, key="bl_view_confidence"
                )
            P_view = np.zeros((1, n))
            P_view[0, idx] = 1.0
            Q_view = np.array([retorno_view - rf_anual])
            c = confianza_view / 100.0
            var_view_prior = float((P_view @ (tau * Sigma_annual) @ P_view.T)[0, 0])
            omega_kk = var_view_prior * (1 - c) / c
            Omega_view = np.array([[omega_kk]])
            st.caption(
                f"Vista: {activo_view} = {retorno_view:.2%} total "
                f"({Q_view[0]:.2%} en exceso sobre rf) · Omega implícita = "
                f"{omega_kk:.6f} (más confianza → menos Omega → más peso a tu vista)."
            )

        try:
            bl_result = black_litterman(Sigma_annual, w_ref, delta, tau, P_view, Q_view, Omega_view)
        except BlackLittermanError as exc:
            st.error(str(exc))
        else:
            mu_bl_total = bl_result.mu_excess + rf_anual
            st.dataframe(
                pd.DataFrame(
                    {"Activo": selected, "μ histórico": mu_annual, "μ BL": mu_bl_total}
                ),
                use_container_width=True, hide_index=True,
            )
            try:
                tan_bl = tangency_portfolio(
                    mu_bl_total, bl_result.Sigma_predictive, rf_anual, bounds=bounds
                )
            except PortfolioOptimizationError as exc:
                st.error(f"El solver no convergió con μ_BL: {exc}")
            else:
                st.write(
                    "Tangente con μ_BL: "
                    + ", ".join(f"{t}={w:.2%}" for t, w in zip(selected, tan_bl.weights))
                    + f" · μ={tan_bl.expected_return:.4%} · σ={tan_bl.volatility:.4%}"
                )
                bl_tan_weights = tan_bl.weights

    st.markdown("**Rebalanceo simulado**")
    st.caption(
        "Ejecución en papel únicamente (mandato v2: execution_mode "
        "paper_only) — no envía órdenes reales."
    )
    target_map = {"Tangente": tan.weights, "Óptimo personal": opt.weights, "GMV": gmv.weights}
    opciones_objetivo = ["Tangente", "Óptimo personal", "GMV"]
    if bl_tan_weights is not None:
        opciones_objetivo.append("Tangente con Black-Litterman")
        target_map["Tangente con Black-Litterman"] = bl_tan_weights
    target_choice = st.radio(
        "Cartera objetivo a rebalancear", options=opciones_objetivo,
        horizontal=True, key="rebalance_target_choice",
    )
    target_weights = target_map[target_choice]

    st.write("Cantidades actuales por activo (edita según tu posición real; 0 por defecto):")
    cantidades_actuales = []
    cols = st.columns(len(selected))
    for col, t in zip(cols, selected):
        with col:
            q = st.number_input(t, min_value=0.0, value=0.0, step=1.0, key=f"rebalance_qty_{t}")
            cantidades_actuales.append(q)

    col1, col2, col3 = st.columns(3)
    with col1:
        caja_actual = st.number_input(
            "Caja disponible", min_value=0.0, value=10000.0, step=100.0, key="rebalance_cash"
        )
    with col2:
        costo_nominal = st.number_input(
            "Costo por nominal operado", min_value=0.0, value=0.001, step=0.0005,
            format="%.4f", key="rebalance_cost",
        )
    with col3:
        permitir_fracciones = st.checkbox("Permitir fracciones", value=True, key="rebalance_fractions")

    precios_actuales = np.array([float(price_df[t].iloc[-1]) for t in selected])

    if st.button("Calcular rebalanceo"):
        try:
            reb = rebalance(
                cantidades=cantidades_actuales,
                precios_nuevos=precios_actuales,
                caja=caja_actual,
                pesos_objetivo=target_weights,
                costo_por_nominal=costo_nominal,
                fracciones=permitir_fracciones,
            )
        except RebalanceError as exc:
            st.error(str(exc))
        else:
            trade_rows = [
                {
                    "Activo": t,
                    "Precio": f"{p:.4f}",
                    "Cantidad actual": f"{q:.4f}",
                    "Cantidad objetivo": f"{qf:.4f}",
                    "Operación": (
                        f"{'Comprar' if trade > 1e-9 else 'Vender' if trade < -1e-9 else 'Sin cambio'} "
                        f"{abs(trade):.4f}"
                    ),
                }
                for t, p, q, qf, trade in zip(
                    selected, precios_actuales, cantidades_actuales,
                    reb.cantidades_finales, reb.trades,
                )
            ]
            st.dataframe(trade_rows, use_container_width=True, hide_index=True)
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Patrimonio antes", f"{reb.patrimonio_pre:,.2f}")
            col2.metric("Patrimonio después", f"{reb.patrimonio_post:,.2f}")
            col3.metric("Costos totales", f"{reb.costos_totales:,.2f}")
            col4.metric("Turnover unilateral", f"{reb.turnover_unilateral:.2%}")
            st.caption(
                f"Caja final: {reb.caja_final:,.2f} · Nominal negociado: {reb.nominal_negociado:,.2f}"
            )

    st.markdown("**Trazabilidad y exportación (GUIA_V2 §11)**")
    trace_params = {
        "rf_anual": rf_anual,
        "gamma": gamma,
        "bounds": "[0,1] por activo (largo, sin apalancamiento)",
    }
    if fx_rates:
        trace_params["fx_base_currency"] = base_currency
        trace_params["fx_rates"] = fx_rates
    if usar_shrinkage:
        trace_params["shrinkage_delta"] = shrink_delta
    if usar_bl:
        trace_params["bl_delta"] = delta
        trace_params["bl_tau"] = tau
        trace_params["bl_view_added"] = bool(bl_tan_weights is not None)

    trace = build_trace_record(
        source=result.ok[selected[0]].source,
        currency=base_currency,
        frequency=frequency,
        return_convention="retornos simples (agregación de cartera, GUIA_V2 §4.1)",
        annualization="lineal (mu x m, Sigma x m)",
        asset_order=selected,
        common_rows=n_obs,
        parameters=trace_params,
        solver="scipy.optimize.minimize (SLSQP) — src/portfolio.py",
        residuals={
            "gmv": {"success": gmv.solver_success, "message": gmv.solver_message},
            "tangente": {"success": tan.solver_success, "message": tan.solver_message},
            "optimo_personal": {"success": opt.solver_success, "message": opt.solver_message},
            "maximo_retorno": {"success": maxret.solver_success, "message": maxret.solver_message},
        },
        test_evidence="tests/unit/test_v2_portfolio.py",
    )
    st.download_button(
        "Descargar trazabilidad de este análisis (JSON)",
        data=json.dumps(trace, indent=2, ensure_ascii=False),
        file_name=f"trazabilidad_portafolio_{trace['analysis_id'][:8]}.json",
        mime="application/json",
        key="portfolio_trace_download",
    )

    portfolio_weights_for_beta = {
        "Mínima varianza (GMV)": gmv.weights,
        "Tangente (máx. Sharpe)": tan.weights,
        f"Óptimo personal (γ={gamma:g})": opt.weights,
        "Máximo retorno esperado": maxret.weights,
    }
    carteras_full = {
        "Mínima varianza (GMV)": gmv,
        "Tangente (máx. Sharpe)": tan,
        f"Óptimo personal (γ={gamma:g})": opt,
        "Máximo retorno esperado": maxret,
    }
    if bl_tan_weights is not None:
        portfolio_weights_for_beta["Tangente con Black-Litterman"] = bl_tan_weights
        carteras_full["Tangente con Black-Litterman"] = tan_bl
    return {
        "tickers": selected,
        "weights": portfolio_weights_for_beta,
        "carteras": carteras_full,
        "rf_anual": rf_anual,
        "gamma": gamma,
        "frequency": frequency,
        "n_obs": n_obs,
        "currency": base_currency,
        "source": result.ok[selected[0]].source,
        "corr_matrix": corr_matrix,
        "fecha_inicio": str(simple_returns.index.min().date()),
        "fecha_fin": str(simple_returns.index.max().date()),
    }


def _render_beta_capm_v2(result: FetchResult | None, portfolio_bundle: dict | None = None) -> dict | None:
    """Mandato v2 (M7, GUIA_V2 §8): beta manual/OLS, apalancamiento
    (Hamada) y CAPM con extensión de país. `portfolio_bundle` (de
    _render_portfolio_v2, si ya se calculó en este mismo run) habilita
    beta contra el portafolio óptimo además de contra otro activo o un
    índice de mercado descargado como activo más."""
    st.header("Beta, CAPM y apalancamiento")

    beta_default = 1.0
    st.markdown("**Beta con tus datos reales**")
    if not result or not result.ok or len(result.ok) < 2:
        st.info(
            "Descarga al menos 2 activos válidos arriba para calcular beta "
            "contra un benchmark real (otro de tus activos descargados)."
        )
    else:
        tickers = sorted(result.ok.keys())
        st.caption(
            "Para beta frente a un índice de mercado, descárgalo como un "
            "activo más arriba (ej. ^GSPC para S&P 500, ^IXIC para "
            "Nasdaq, ^DJI para Dow Jones) y elígelo como benchmark aquí."
        )
        bench_mode_options = ["Otro activo descargado"]
        has_portfolio = bool(portfolio_bundle and len(portfolio_bundle.get("tickers", [])) >= 2)
        if has_portfolio:
            bench_mode_options.append("Portafolio óptimo (sección anterior)")
        bench_mode = (
            st.radio("Tipo de benchmark", options=bench_mode_options, horizontal=True, key="beta_bench_mode")
            if len(bench_mode_options) > 1 else bench_mode_options[0]
        )

        col1, col2 = st.columns(2)
        with col1:
            activo = st.selectbox("Activo", options=tickers, key="beta_asset")

        bench_returns_series = None
        benchmark_label = None
        if bench_mode == "Portafolio óptimo (sección anterior)":
            with col2:
                cartera_nombre = st.selectbox(
                    "Cartera objetivo", options=list(portfolio_bundle["weights"].keys()),
                    key="beta_benchmark_portfolio",
                )
            port_tickers = portfolio_bundle["tickers"]
            faltantes = [t for t in port_tickers if t not in result.ok]
            if faltantes:
                st.error(
                    f"Faltan datos descargados para: {', '.join(faltantes)} "
                    "(se quitaron de tus activos después de calcular el portafolio)."
                )
            else:
                port_price_df = pd.DataFrame({t: result.ok[t].prices for t in port_tickers})
                port_simple_returns = port_price_df.pct_change(fill_method=None)
                port_common_mask = port_simple_returns.notna().all(axis=1)
                port_simple_returns = port_simple_returns.loc[port_common_mask]
                bench_returns_series = pd.Series(
                    portfolio_log_returns(
                        port_simple_returns.to_numpy(), portfolio_bundle["weights"][cartera_nombre]
                    ),
                    index=port_simple_returns.index,
                )
                benchmark_label = f"cartera «{cartera_nombre}»"
        else:
            with col2:
                bench_options = [t for t in tickers if t != activo]
                benchmark = st.selectbox(
                    "Benchmark (otro activo ya descargado)", options=bench_options, key="beta_benchmark"
                )
            bench_returns_series = compute_log_returns(result.ok[benchmark].prices)
            benchmark_label = benchmark

        if bench_returns_series is not None:
            asset_returns_series = compute_log_returns(result.ok[activo].prices)
            common_returns_idx = asset_returns_series.index.intersection(bench_returns_series.index)
            asset_returns = asset_returns_series.loc[common_returns_idx].to_numpy()
            bench_returns = bench_returns_series.loc[common_returns_idx].to_numpy()

            try:
                beta_cov = beta_covariance(asset_returns, bench_returns)
                ols = beta_ols(asset_returns, bench_returns)
            except BetaCapmError as exc:
                st.error(str(exc))
            else:
                st.dataframe(
                    [
                        {"Método": "Cov/Var", "Beta": f"{beta_cov:.4f}", "Alpha": "—", "R²": "—", "Error estándar": "—"},
                        {
                            "Método": "OLS con intercepto",
                            "Beta": f"{ols.beta:.4f}",
                            "Alpha": f"{ols.alpha:.6f}",
                            "R²": f"{ols.r_squared:.4f}",
                            "Error estándar": f"{ols.std_err:.4f}",
                        },
                    ],
                    use_container_width=True, hide_index=True,
                )
                st.caption(
                    f"Beta de {activo} frente a {benchmark_label} (n={ols.n} "
                    "retornos log comunes). Cov/Var y OLS deben coincidir "
                    "exactamente para una sola variable (P98); R² bajo con "
                    "pocas observaciones no acredita precisión suficiente (P103)."
                )
                beta_default = beta_cov

    st.markdown("**Apalancamiento (Hamada)**")
    st.caption(
        "Valores por defecto ilustrativos — edítalos con los de tu caso."
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        beta_L_input = st.number_input(
            "Beta apalancada (del comparable)", value=float(beta_default),
            step=0.05, format="%.4f", key="hamada_beta_l",
        )
    with col2:
        tax = st.number_input(
            "Tasa de impuesto", min_value=0.0, max_value=0.99, value=0.35,
            step=0.01, key="hamada_tax",
        )
    with col3:
        beta_D = st.number_input(
            "Beta de la deuda (0 = sin riesgo sistemático)", value=0.0,
            step=0.05, key="hamada_beta_d",
        )
    col1, col2 = st.columns(2)
    with col1:
        de_comparable = st.number_input(
            "D/E del comparable (para desapalancar)", min_value=0.0, value=0.6,
            step=0.05, key="hamada_de_comparable",
        )
    with col2:
        de_objetivo = st.number_input(
            "D/E objetivo (para reapalancar)", min_value=0.0, value=0.75,
            step=0.05, key="hamada_de_objetivo",
        )

    beta_U = None
    beta_L_obj = None
    beta_U_para_relever = None
    try:
        beta_U = unlever_beta(beta_L_input, tax, de_comparable, beta_D=beta_D)
    except BetaCapmError as exc:
        st.error(str(exc))
    else:
        st.metric("Beta desapalancada del comparable (beta_U)", f"{beta_U:.4f}")

        usar_beta_sector = st.checkbox(
            "Usar en su lugar un beta sectorial de referencia externo "
            "(ej. Damodaran) para reapalancar",
            key="hamada_usar_beta_sector",
        )
        beta_U_para_relever = beta_U
        if usar_beta_sector:
            beta_U_para_relever = st.number_input(
                "Beta sectorial (ingrésalo tú — esta app no lo descarga "
                "automáticamente de Damodaran ni de ninguna otra fuente)",
                min_value=0.0, value=float(beta_U), step=0.05, format="%.4f",
                key="hamada_beta_sector_value",
            )
            st.caption(
                "Reemplaza el beta_U calculado del comparable de arriba "
                "únicamente para el paso de reapalancamiento — consulta tú "
                "la fuente (ej. pages.stern.nyu.edu/~adamodar/, tabla de "
                "betas por sector) y transcribe el valor aquí."
            )

        try:
            beta_L_obj = relever_beta(beta_U_para_relever, tax, de_objetivo, beta_D=beta_D)
        except BetaCapmError as exc:
            st.error(str(exc))
        else:
            st.metric("Beta reapalancada a D/E objetivo", f"{beta_L_obj:.4f}")

    st.markdown("**CAPM y costo de patrimonio (Ke)**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        rf = st.number_input(
            "rf", min_value=0.0, value=0.043, step=0.001, format="%.4f", key="capm_rf"
        )
    with col2:
        erp = st.number_input(
            "ERP (prima de mercado madura)", min_value=0.0, value=0.055,
            step=0.001, format="%.4f", key="capm_erp",
        )
    with col3:
        crp = st.number_input(
            "CRP (riesgo país)", min_value=0.0, value=0.032, step=0.001,
            format="%.4f", key="capm_crp",
        )
    with col4:
        lam = st.number_input(
            "lambda (exposición al riesgo país)", min_value=0.0, value=1.0,
            step=0.1, key="capm_lambda",
        )

    beta_for_capm = beta_L_obj if beta_L_obj is not None else beta_L_input
    ke_foreign = capm_ke(rf, beta_for_capm, erp, country_risk_premium=crp, lambda_=lam)
    st.metric("Ke (moneda de rf)", f"{ke_foreign:.4%}")

    ke_converted = None
    with st.expander("Convertir Ke a otra moneda por paridad de inflación (opcional)"):
        col1, col2 = st.columns(2)
        with col1:
            infl_dom = st.number_input(
                "Inflación moneda destino", min_value=-0.5, value=0.045,
                step=0.001, format="%.4f", key="capm_infl_dom",
            )
        with col2:
            infl_for = st.number_input(
                "Inflación moneda de origen (rf)", min_value=-0.5, value=0.025,
                step=0.001, format="%.4f", key="capm_infl_for",
            )
        try:
            ke_converted = convert_ke_by_inflation(ke_foreign, infl_dom, infl_for)
        except BetaCapmError as exc:
            st.error(str(exc))
        else:
            st.metric("Ke convertida", f"{ke_converted:.4%}")
        st.caption(
            "Supuesto de consistencia nominal (paridad de tasas), no una "
            "predicción cierta de tipo de cambio (P111)."
        )

    st.markdown("**Meta de utilidad: beta desapalancada vs. reapalancada**")
    st.caption(
        "Ke×patrimonio_libros es una meta PRESUPUESTAL del caso, no "
        "equivalencia general entre ROE contable y rentabilidad exigida "
        "de mercado (GUIA_V2 §9.1) — compara el piso de rentabilidad "
        "exigido si la empresa operara sin deuda (β desapalancada) "
        "contra el exigido con su apalancamiento real (β reapalancada)."
    )
    patrimonio_libros = st.number_input(
        "Patrimonio en libros", min_value=0.0, value=60000.0, step=1000.0,
        key="capm_patrimonio_libros",
    )
    if beta_U_para_relever is None or beta_L_obj is None:
        st.info("Resuelve primero el bloque de Hamada arriba (desapalancar/reapalancar) para ver esta comparación.")
    else:
        try:
            filas_meta = []
            for nombre, beta_i in [("Sector (β desapalancada)", beta_U_para_relever), ("Empresa (β reapalancada)", beta_L_obj)]:
                ke_sin_pais = capm_ke(rf, beta_i, erp)
                ke_con_pais = capm_ke(rf, beta_i, erp, country_risk_premium=crp, lambda_=lam)
                ke_cop_i = convert_ke_by_inflation(ke_con_pais, infl_dom, infl_for)
                filas_meta.append(
                    {
                        "Escenario": nombre,
                        "Beta": f"{beta_i:.4f}",
                        "Ke (sin país)": f"{ke_sin_pais:.2%}",
                        "Utilidad req. (sin país)": f"{ke_sin_pais*patrimonio_libros:,.0f}",
                        "Ke + país": f"{ke_con_pais:.2%}",
                        "Ke (moneda local)": f"{ke_cop_i:.2%}",
                        "Utilidad req. (moneda local)": f"{ke_cop_i*patrimonio_libros:,.0f}",
                    }
                )
        except BetaCapmError as exc:
            st.error(str(exc))
        else:
            st.dataframe(filas_meta, use_container_width=True, hide_index=True)

    return {
        "ke_foreign": ke_foreign,
        "ke_converted": ke_converted,
        "rf": rf,
        "tax": tax,
        "de_objetivo": de_objetivo,
        "beta_L_obj": beta_L_obj,
    }


def _render_sml_desempeno_v2(
    result: FetchResult | None, date_config: dict | None, portfolio_bundle: dict | None
) -> None:
    """Sustentación final, núcleo financiero de referencia: Línea del
    Mercado de Títulos (SML, CAPM para todos los activos) y desempeño
    de la cartera vs. benchmark (Treynor, Jensen, Information Ratio)."""
    st.header("Línea del Mercado de Títulos (SML) y desempeño vs. benchmark")

    if not result or not result.ok or len(result.ok) < 2:
        st.info("Descarga al menos 2 activos válidos arriba para esta sección.")
        return

    tickers = sorted(result.ok.keys())
    col1, col2 = st.columns(2)
    with col1:
        benchmark = st.selectbox("Benchmark / proxy de mercado", options=tickers, key="perf_benchmark")
    with col2:
        rf = st.number_input(
            "rf anual", min_value=0.0, value=0.03, step=0.005, format="%.4f", key="perf_rf"
        )
    frequency = date_config["frecuencia"] if date_config else "Diaria"
    m = FRECUENCIAS.get(frequency, 252)

    bench_prices = result.ok[benchmark].prices
    bench_simple = bench_prices.pct_change(fill_method=None).dropna()
    if len(bench_simple) < 3:
        st.warning(f"{benchmark} no tiene suficientes observaciones para usarse como benchmark.")
        return
    mu_m = float(bench_simple.mean() * m)
    st.caption(
        f"E[Rm] histórico anualizado ({benchmark}): {mu_m:.2%} · rf: {rf:.2%} · "
        f"prima de mercado implícita (E[Rm]-rf): {mu_m - rf:.2%} · retornos "
        "simples (misma convención de Markowitz, GUIA_V2 §4.1), no logarítmicos."
    )

    st.markdown("**SML: beta y rendimiento requerido por activo (CAPM)**")
    rows = []
    for t in tickers:
        if t == benchmark:
            continue
        asset_simple = result.ok[t].prices.pct_change(fill_method=None).dropna()
        common_idx = asset_simple.index.intersection(bench_simple.index)
        if len(common_idx) < 3:
            continue
        a = asset_simple.loc[common_idx].to_numpy()
        b = bench_simple.loc[common_idx].to_numpy()
        try:
            ols = beta_ols(a, b)
        except BetaCapmError:
            continue
        mu_hist = float(asset_simple.loc[common_idx].mean() * m)
        required = capm_ke(rf, ols.beta, mu_m - rf)
        risk_split = systematic_risk_share(min(max(ols.r_squared, 0.0), 1.0))
        rows.append(
            {
                "Activo": t, "Beta": ols.beta, "R2": ols.r_squared,
                "Riesgo sistematico": risk_split["sistematico"],
                "Riesgo no sistematico": risk_split["no_sistematico"],
                "mu historico": mu_hist, "Requerido CAPM": required,
                "Alfa (historico-requerido)": mu_hist - required,
            }
        )

    if not rows:
        st.info("Ningún activo tiene suficientes observaciones comunes con el benchmark elegido.")
    else:
        sml_df = pd.DataFrame(rows)
        st.dataframe(
            sml_df.assign(**{
                "Beta": sml_df["Beta"].map("{:.4f}".format),
                "R2": sml_df["R2"].map("{:.4f}".format),
                "Riesgo sistematico": sml_df["Riesgo sistematico"].map("{:.2%}".format),
                "Riesgo no sistematico": sml_df["Riesgo no sistematico"].map("{:.2%}".format),
                "mu historico": sml_df["mu historico"].map("{:.2%}".format),
                "Requerido CAPM": sml_df["Requerido CAPM"].map("{:.2%}".format),
                "Alfa (historico-requerido)": sml_df["Alfa (historico-requerido)"].map("{:+.2%}".format),
            }),
            use_container_width=True, hide_index=True,
        )
        beta_line = np.linspace(0.0, max(float(sml_df["Beta"].max()), 1.0) * 1.2, 2)
        sml_line_df = pd.DataFrame({"Beta": beta_line, "Requerido": capm_ke(rf, beta_line, mu_m - rf)})
        line = alt.Chart(sml_line_df).mark_line(color="green").encode(
            x=alt.X("Beta", title="Beta vs. benchmark"), y=alt.Y("Requerido", title="Retorno anual"),
        )
        points = alt.Chart(sml_df).mark_point(size=100, filled=True).encode(
            x="Beta", y=alt.Y("mu historico", title="Retorno anual"),
            tooltip=["Activo", "Beta", "mu historico", "Requerido CAPM"],
        )
        labels = alt.Chart(sml_df).mark_text(dy=-10, fontSize=10).encode(x="Beta", y="mu historico", text="Activo")
        st.altair_chart(line + points + labels, use_container_width=True)
        st.caption(
            "Línea verde: SML (rendimiento requerido por CAPM según beta). "
            "Puntos: retorno histórico real de cada activo. Por encima de la "
            "línea = alfa histórico positivo (rindió más de lo que su beta "
            "exigía); por debajo = negativo. R² = participación del riesgo "
            "total explicada por el mercado (riesgo sistemático); 1-R² es "
            "riesgo idiosincrático, diversificable."
        )

    st.markdown("**Desempeño de la cartera vs. benchmark: Treynor, Jensen, Information Ratio**")
    if not portfolio_bundle or not portfolio_bundle.get("carteras"):
        st.info("Calcula un portafolio en 'Portafolio v2' arriba para ver esta comparación.")
        return

    cartera_nombre = st.selectbox(
        "Cartera", options=list(portfolio_bundle["carteras"].keys()), key="perf_cartera"
    )
    cartera = portfolio_bundle["carteras"][cartera_nombre]
    port_tickers = portfolio_bundle["tickers"]
    faltantes = [t for t in port_tickers if t not in result.ok]
    if faltantes:
        st.error(f"Faltan datos descargados para: {', '.join(faltantes)}.")
        return

    port_price_df = pd.DataFrame({t: result.ok[t].prices for t in port_tickers})
    port_simple = port_price_df.pct_change(fill_method=None)
    port_simple = port_simple.loc[port_simple.notna().all(axis=1)]
    port_returns = pd.Series(
        portfolio_simple_returns(port_simple.to_numpy(), cartera.weights), index=port_simple.index
    )
    common_idx = port_returns.index.intersection(bench_simple.index)
    if len(common_idx) < 3:
        st.warning("Observaciones comunes insuficientes entre la cartera y el benchmark.")
        return

    p = port_returns.loc[common_idx].to_numpy()
    b = bench_simple.loc[common_idx].to_numpy()
    try:
        beta_p = beta_covariance(p, b)
        ols_p = beta_ols(p, b)
    except BetaCapmError as exc:
        st.error(str(exc))
        return

    sharpe_p = (
        (cartera.expected_return - rf) / cartera.volatility if cartera.volatility > 0 else float("nan")
    )
    jensen_p = jensens_alpha(cartera.expected_return, rf, beta_p, mu_m)
    active_returns = p - b

    col1, col2, col3 = st.columns(3)
    col1.metric("Sharpe (riesgo total)", f"{sharpe_p:.4f}" if not np.isnan(sharpe_p) else "—")
    try:
        treynor_p = treynor_ratio(cartera.expected_return, rf, beta_p)
        col2.metric("Treynor (riesgo sistemático)", f"{treynor_p:.4f}")
    except PerformanceError as exc:
        col2.metric("Treynor", "—")
        col2.caption(str(exc))
    col3.metric("Alfa de Jensen", f"{jensen_p:+.2%}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Beta de la cartera vs. benchmark", f"{beta_p:.4f}")
    col2.metric("R² (riesgo sistemático)", f"{ols_p.r_squared:.4f}")
    try:
        ir_result = information_ratio(active_returns, m)
        col3.metric("Information Ratio", f"{ir_result.information_ratio:.4f}")
    except PerformanceError as exc:
        col3.metric("Information Ratio", "—")
        col3.caption(str(exc))

    st.caption(
        "Treynor y Jensen usan beta (riesgo sistemático) en vez de sigma "
        "(riesgo total, como Sharpe) — penalizan solo el riesgo que no se "
        "diversifica. Information Ratio compara la cartera contra el "
        "benchmark periodo a periodo (retorno activo / tracking error), no "
        "contra rf."
    )


def _render_valuation_v2(capm_bundle: dict | None = None) -> None:
    """Mandato v2 (M8, GUIA_V2 §9): FCFF -> WACC -> valor terminal ->
    valor del patrimonio, GENERALIZADO a cualquier caso — ningún valor
    viene precargado de un caso específico; `capm_bundle` (de
    _render_beta_capm_v2, si ya se calculó en este mismo run) solo
    sugiere un Ke/D-E/tax de partida, editables."""
    st.header("Valoración: de CAPM al valor del patrimonio")
    st.caption(
        "Generalizado — ingresa los parámetros de tu propio caso abajo; "
        "nada viene precargado de un caso particular (GUIA_V2 §9)."
    )

    st.markdown("**1. Proyección operativa** (bucle ventas-capacidad-CAPEX-depreciación)")
    col1, col2, col3 = st.columns(3)
    with col1:
        sales0 = st.number_input(
            "Ventas año 0", min_value=0.01, value=100000.0, step=1000.0, key="val_sales0"
        )
    with col2:
        capacity0 = st.number_input(
            "Capacidad de ventas año 0", min_value=0.01, value=120000.0, step=1000.0, key="val_capacity0"
        )
    with col3:
        variable_cost_rate = st.number_input(
            "Costo variable (% de ventas)", min_value=0.0, max_value=0.99, value=0.6,
            step=0.01, key="val_varcost",
        )
    col1, col2, col3 = st.columns(3)
    with col1:
        fixed_costs = st.number_input(
            "Gastos fijos", min_value=0.0, value=15000.0, step=500.0, key="val_fixed"
        )
    with col2:
        depreciation0 = st.number_input(
            "Depreciación año 0", min_value=0.0, value=6000.0, step=100.0, key="val_dep0"
        )
    with col3:
        tax_default = capm_bundle.get("tax", 0.35) if capm_bundle else 0.35
        tax_val = st.number_input(
            "Tasa de impuesto", min_value=0.0, max_value=0.99, value=float(tax_default),
            step=0.01, key="val_tax",
        )
    col1, col2, col3 = st.columns(3)
    with col1:
        nwc_sales_rate = st.number_input(
            "NWC (% de ventas)", min_value=0.0, max_value=1.0, value=0.1, step=0.01, key="val_nwc"
        )
    with col2:
        capex_per_unit_expansion = st.number_input(
            "CAPEX por unidad de capacidad adicional", min_value=0.0, value=0.7,
            step=0.05, key="val_capex_unit",
        )
    with col3:
        useful_life_years = st.number_input(
            "Vida útil de la expansión (años)", min_value=1, value=10, step=1, key="val_life"
        )

    horizonte = st.slider(
        "Horizonte de proyección (años)", min_value=1, max_value=10, value=5, key="val_horizon"
    )
    st.write("Crecimiento de ventas por año:")
    sales_growth_rates = []
    for i, col in enumerate(st.columns(horizonte), start=1):
        with col:
            g = st.number_input(
                f"Año {i}", min_value=-0.99, value=0.05, step=0.01, format="%.4f",
                key=f"val_growth_{i}",
            )
            sales_growth_rates.append(g)

    try:
        projections = project_years(
            sales_growth_rates=sales_growth_rates, sales0=sales0, capacity0=capacity0,
            variable_cost_rate=variable_cost_rate, fixed_costs=fixed_costs,
            depreciation0=depreciation0, tax=tax_val, nwc_sales_rate=nwc_sales_rate,
            capex_per_unit_expansion=capex_per_unit_expansion,
            useful_life_years=int(useful_life_years),
        )
    except ValuationError as exc:
        st.error(str(exc))
        return

    st.dataframe(
        [
            {
                "Año": p.year, "Ventas": f"{p.sales:,.0f}", "EBIT": f"{p.ebit:,.0f}",
                "Depreciación": f"{p.depreciation:,.0f}", "CAPEX": f"{p.capex:,.0f}",
                "ΔNWC": f"{p.delta_nwc:,.0f}", "FCFF": f"{p.fcff:,.0f}",
                "Capacidad fin de año": f"{p.capacity_end:,.0f}",
            }
            for p in projections
        ],
        use_container_width=True, hide_index=True,
    )

    st.markdown("**2. WACC**")
    ke_default = 0.12
    de_default = 0.75
    if capm_bundle:
        ke_default = capm_bundle.get("ke_converted") or capm_bundle.get("ke_foreign") or ke_default
        de_default = capm_bundle.get("de_objetivo") or de_default
        st.caption(
            "Ke y D/E sugeridos a partir de la sección de Beta/CAPM de "
            "arriba — edítalos si tu caso usa otros valores."
        )
    col1, col2, col3 = st.columns(3)
    with col1:
        ke = st.number_input(
            "Ke (costo de patrimonio)", min_value=0.0, value=float(ke_default),
            step=0.001, format="%.4f", key="val_ke",
        )
    with col2:
        kd = st.number_input(
            "Kd (costo de deuda, antes de impuesto)", min_value=0.0, value=0.09,
            step=0.001, format="%.4f", key="val_kd",
        )
    with col3:
        de_val = st.number_input(
            "D/E (estructura de capital objetivo)", min_value=0.0, value=float(de_default),
            step=0.05, key="val_de",
        )

    try:
        wacc_val = wacc(E=1.0, D=de_val, Ke=ke, Kd=kd, tax=tax_val)
    except ValuationError as exc:
        st.error(str(exc))
        return
    st.metric("WACC", f"{wacc_val:.4%}")

    st.markdown("**3. Valor terminal y valor del patrimonio**")
    col1, col2 = st.columns(2)
    with col1:
        g_terminal = st.number_input(
            "g (crecimiento perpetuo terminal, < WACC)", min_value=-0.5, value=0.03,
            step=0.005, format="%.4f", key="val_g",
        )
    with col2:
        deuda_neta = st.number_input(
            "Deuda neta (firma -> patrimonio)", min_value=0.0, value=0.0,
            step=1000.0, key="val_netdebt",
        )

    fcff_series = [p.fcff for p in projections]
    try:
        fcff_next = fcff_series[-1] * (1 + g_terminal)
        tv = terminal_value_gordon(fcff_next, wacc_val, g_terminal)
    except ValuationError as exc:
        st.error(str(exc))
        return

    cashflows_con_tv = list(fcff_series)
    cashflows_con_tv[-1] += tv
    valor_firma = present_value(cashflows_con_tv, wacc_val)
    valor_patrimonio = valor_firma - deuda_neta

    col1, col2, col3 = st.columns(3)
    col1.metric("Valor terminal (en el año H)", f"{tv:,.0f}")
    col2.metric("Valor de la firma (VP de FCFF+TV)", f"{valor_firma:,.0f}")
    col3.metric("Valor del patrimonio", f"{valor_patrimonio:,.0f}")
    st.caption(
        "Valor del patrimonio = VP(FCFF años 1..H + valor terminal en H, "
        "descontados a WACC) - deuda neta. No es garantía ni "
        "recomendación de inversión."
    )


_ANEXO1_TEXTO_OBLIGATORIO = (
    "La ficha técnica puede servir al inversionista para conocer los "
    "objetivos, riesgos, costos y otras condiciones relevantes para "
    "evaluar una potencial inversión en el FIC. Este documento no debe "
    "ser la única fuente de información para la toma de decisiones de "
    "inversión. La información incluida refleja el comportamiento "
    "histórico del FIC, pero no implica que su comportamiento en el "
    "futuro sea igual o semejante."
)

_FIC_ADVERTENCIA = (
    'Adaptado del Artículo 3.1.1.9.3 del Decreto 1242 de 2013: "Las '
    "obligaciones [...] relacionadas con la gestión del portafolio son "
    "de medio y no, de resultado. Los dineros entregados [...] no son "
    "depósitos, ni generan [...] las obligaciones propias de una "
    "institución de depósito y no están amparados por el seguro de "
    "depósito del Fondo de Garantías de Instituciones Financieras "
    "(Fogafín), ni por ningún otro esquema de naturaleza. La inversión "
    '[...] está sujeta a los riesgos de inversión, derivados de la '
    'evolución de los precios de los activos que componen el '
    'portafolio [...]".'
)


def _build_ficha_dict(
    etiqueta: str, cartera, objetivo: str, portfolio_bundle: dict, capm_bundle: dict | None,
    result: FetchResult, var_conf: float, var_capital: float,
) -> dict:
    """Ficha siguiendo la numeración del Anexo 1 "Ficha Técnica — Fondos
    de Inversión Colectiva" (Parte III, Título VI, Capítulo III de la
    Circular Básica Jurídica, Superintendencia Financiera de Colombia,
    2022) — el documento que reemplaza al antiguo Anexo 6 citado en la
    Guía de Sustentación Final. Se completa lo que un portafolio
    SIMULADO con fines académicos puede calcular; el resto queda N/A
    con el motivo, siguiendo la propia instrucción del Anexo ("si el
    FIC no cuenta con... se debe incluir N/A")."""
    tickers = portfolio_bundle["tickers"]
    rf_anual = portfolio_bundle["rf_anual"]
    sharpe = (
        (cartera.expected_return - rf_anual) / cartera.volatility if cartera.volatility > 0 else None
    )
    var_result = portfolio_var(cartera.expected_return, cartera.volatility, var_conf, var_capital)
    n = len(tickers)
    corr_matrix = portfolio_bundle.get("corr_matrix")
    avg_corr = float((corr_matrix.sum() - n) / (n * (n - 1))) if corr_matrix is not None and n > 1 else None
    beta_L_obj = capm_bundle.get("beta_L_obj") if capm_bundle else None
    ke_show = (capm_bundle.get("ke_converted") or capm_bundle.get("ke_foreign")) if capm_bundle else None

    price_df = pd.DataFrame({t: result.ok[t].prices for t in tickers})
    simple = price_df.pct_change(fill_method=None)
    simple = simple.loc[simple.notna().all(axis=1)]
    port_returns = pd.Series(
        portfolio_simple_returns(simple.to_numpy(), cartera.weights), index=simple.index
    )
    unit_value = var_capital * (1.0 + port_returns).cumprod()
    mdd = max_drawdown(unit_value)
    concentracion = sorted(zip(tickers, cartera.weights), key=lambda x: -x[1])[:10]

    return {
        "1_encabezado": {
            "1.1_identificacion": "Ficha Técnica – Fondos de Inversión Colectiva",
            "1.1_texto_obligatorio": _ANEXO1_TEXTO_OBLIGATORIO,
            "1.2_nombre_fic": f"Botiverso — Cartera {etiqueta} (simulación académica, NO es un FIC real)",
            "1.3_naturaleza": "N/A — simulación académica, no es un FIC regulado; sin pacto de permanencia",
            "1.4_clasificacion_industria": "N/A",
            "1.5_fecha_corte": date.today().isoformat(),
            "1.6_sociedad_administradora": "N/A — no hay sociedad administradora real",
            "1.7_gestor": "N/A",
        },
        "2_informacion_general": {
            "2.1_fecha_inicio_operaciones": portfolio_bundle["fecha_inicio"],
            "2.2_fecha_vencimiento": "N/A — sin vencimiento definido",
            "2.3_tipos_participaciones": "N/A — una sola clase",
            "2.4_valor_activos": float(var_capital),
            "2.5_valor_pasivos": 0.0,
            "2.6_valor_neto": float(var_capital),
            "2.7_valor_unidad": "N/A — no se modela por unidades",
            "2.8_numero_inversionistas": "N/A",
            "2.9_inscripcion_rnve": "N/A",
            "2.10_mercado_secundario": "N/A",
            "2.11_sancion_retiro_anticipado": "N/A — sin pacto de permanencia",
        },
        "3_calificacion": "N/A — no hay calificadora de riesgo autorizada evaluando esta simulación",
        "4_politica_inversion": {
            "4.1_objeto_estrategia": objetivo,
            "4.2_perfil_riesgo": f"Volatilidad anual {cartera.volatility:.2%}",
            "4.3_indice_referencia": "N/A en esta ficha — ver sección 'Línea del Mercado de Títulos (SML) y desempeño vs. benchmark'",
            "4.4_horizonte_recomendado": "1 año (horizonte de las métricas anualizadas)",
        },
        "5_riesgos": {
            "5.1_perfil_liquidez": "100% en rango '1 día o menos' — activos: acciones listadas en bolsa (simplificación: esta app no modela activos ilíquidos)",
            "5.1.2_apalancamiento_bruto": 0.0,
            "5.1.2_apalancamiento_neto": 0.0,
            "5.1.3_maximum_drawdown": float(mdd),
            "5.1.3_var": var_result,
        },
        "6_gastos_comisiones": "N/A — no hay sociedad administradora real cobrando comisión",
        "7_evolucion_historica": {
            "inversion_hipotetica": float(var_capital),
            "valor_final": float(unit_value.iloc[-1]),
            "serie": {str(k.date()): float(v) for k, v in unit_value.items()},
        },
        "8_rentabilidades_y_desempeno": {
            "rentabilidad_esperada_anual": float(cartera.expected_return),
            "sharpe": None if sharpe is None or np.isnan(sharpe) else float(sharpe),
            "nota": "Treynor, alfa de Jensen e Information Ratio vs. benchmark están en la sección 'Línea del Mercado de Títulos (SML) y desempeño vs. benchmark'.",
        },
        "9_volatilidad_historica": {"anual": float(cartera.volatility)},
        "10_inversiones_del_fic": {
            "10.1_composicion_por_clase": "100% renta variable (acciones)",
            "10.5_sectores_economicos": "N/A — clasificación sectorial no disponible en los datos de origen (Yahoo Finance, en este pipeline)",
        },
        "11_principales_inversiones": {
            "11.1_concentracion_top10": {t: float(w) for t, w in concentracion},
            "11.2_a_11.5_renta_fija": "N/A — portafolio de renta variable, no aplican plazos ni duración de Macaulay",
        },
        "12_informacion_adicional": "Repositorio y documentación: https://github.com/mtobon2005-creator/robot-analitico-tbs-eia",
        "13_observaciones": (
            "Ficha adaptada de la estructura del Anexo 1 \"Ficha Técnica — "
            "Fondos de Inversión Colectiva\" (Circular Básica Jurídica, "
            "Superintendencia Financiera de Colombia, 2022) para un "
            "portafolio SIMULADO con fines académicos — no es la ficha "
            "técnica de un FIC real. " + _FIC_ADVERTENCIA
        ),
        "composicion": {t: float(w) for t, w in zip(tickers, cartera.weights)},
        "correlacion_promedio": avg_corr,
        "beta_reapalancada": beta_L_obj,
        "ke": ke_show,
    }


def _render_fic_card(etiqueta: str, ficha: dict) -> None:
    s1, s2, s4, s5, s7, s8, s9, s10, s11 = (
        ficha["1_encabezado"], ficha["2_informacion_general"], ficha["4_politica_inversion"],
        ficha["5_riesgos"], ficha["7_evolucion_historica"], ficha["8_rentabilidades_y_desempeno"],
        ficha["9_volatilidad_historica"], ficha["10_inversiones_del_fic"], ficha["11_principales_inversiones"],
    )

    st.markdown(f"#### 1. Encabezado — {s1['1.2_nombre_fic']}")
    st.caption(s1["1.1_texto_obligatorio"])
    st.caption(
        f"1.3 Naturaleza: {s1['1.3_naturaleza']} · 1.5 Fecha de corte: "
        f"{s1['1.5_fecha_corte']} · 1.6 Sociedad administradora: {s1['1.6_sociedad_administradora']}"
    )

    st.markdown("**2. Información general del FIC**")
    st.caption(
        f"2.1 Inicio de operaciones (datos usados): {s2['2.1_fecha_inicio_operaciones']} · "
        f"2.4 Valor de activos: {s2['2.4_valor_activos']:,.0f} · 2.5 Pasivos: "
        f"{s2['2.5_valor_pasivos']:,.0f} · 2.6 Valor neto: {s2['2.6_valor_neto']:,.0f}"
    )
    st.caption("3. Calificación: " + ficha["3_calificacion"])

    st.markdown("**4. Política de inversión del FIC**")
    st.caption(f"4.1 Objeto y estrategia: {s4['4.1_objeto_estrategia']}")
    st.caption(f"4.2 Perfil de riesgo: {s4['4.2_perfil_riesgo']} · 4.4 Horizonte: {s4['4.4_horizonte_recomendado']}")

    st.markdown("**5. Riesgos**")
    col1, col2, col3 = st.columns(3)
    col1.metric("5.1.2 Apalancamiento neto", f"{s5['5.1.2_apalancamiento_neto']:.0%}")
    col2.metric("5.1.3 Maximum Drawdown", f"{s5['5.1.3_maximum_drawdown']:.2%}")
    var_result = s5["5.1.3_var"]
    col3.metric(f"5.1.3 VaR {int(var_result['confidence']*100)}%", f"{var_result['fraction']:.2%}")
    st.caption(f"5.1 Perfil de liquidez: {s5['5.1_perfil_liquidez']}")

    st.markdown("**7. Evolución histórica** (inversión hipotética)")
    serie_df = pd.DataFrame(
        {"fecha": list(s7["serie"].keys()), "valor": list(s7["serie"].values())}
    )
    serie_df["fecha"] = pd.to_datetime(serie_df["fecha"])
    chart = alt.Chart(serie_df).mark_line().encode(
        x=alt.X("fecha:T", title="Fecha"), y=alt.Y("valor:Q", title=f"Valor de {s7['inversion_hipotetica']:,.0f}"),
    )
    st.altair_chart(chart, use_container_width=True)
    st.caption(f"Valor final: {s7['valor_final']:,.2f} (inicial: {s7['inversion_hipotetica']:,.2f})")

    st.markdown("**8-9. Rentabilidades y volatilidad histórica**")
    col1, col2, col3 = st.columns(3)
    col1.metric("Rentabilidad esperada anual", f"{s8['rentabilidad_esperada_anual']:.2%}")
    col2.metric("Volatilidad anual (9)", f"{s9['anual']:.2%}")
    col3.metric("Sharpe", f"{s8['sharpe']:.3f}" if s8["sharpe"] is not None else "—")
    st.caption(s8["nota"])

    st.markdown("**10-11. Inversiones del FIC y principales posiciones**")
    st.caption(f"10.1 Composición por clase de activo: {s10['10.1_composicion_por_clase']}")
    top10_df = pd.DataFrame(
        [{"Activo": t, "Peso": f"{w:.2%}"} for t, w in s11["11.1_concentracion_top10"].items()]
    )
    st.dataframe(top10_df, use_container_width=True, hide_index=True)

    beta_L_obj, ke_show, avg_corr = ficha["beta_reapalancada"], ficha["ke"], ficha["correlacion_promedio"]
    if beta_L_obj is not None or ke_show is not None or avg_corr is not None:
        col1, col2, col3 = st.columns(3)
        col1.metric("Correlación promedio", f"{avg_corr:.3f}" if avg_corr is not None else "—")
        col2.metric("Beta reapalancada", f"{beta_L_obj:.4f}" if beta_L_obj is not None else "—")
        col3.metric("Ke", f"{ke_show:.2%}" if ke_show is not None else "—")

    with st.expander("¿Por qué hay secciones en N/A? (resto del Anexo 1)"):
        st.markdown(
            "El Anexo 1 tiene 13 secciones; esta ficha completa las que un "
            "portafolio **simulado** puede tener y marca N/A el resto, con "
            "el motivo — no se inventa:\n\n"
            "- **No aplica por no ser un FIC real administrado** (secciones "
            "1.3, 1.4, 1.6, 1.7, 2.2, 2.3, 2.7 a 2.11, 3, 6): naturaleza, "
            "clasificación de industria, sociedad administradora, gestor, "
            "vencimiento, tipos de participación, valor de la unidad, "
            "número de inversionistas, inscripción en el RNVE, mercado "
            "secundario, sanciones, calificación de riesgo y comisiones.\n"
            "- **No aplica por ser un portafolio solo de acciones** "
            "(secciones 10.5, 11.2 a 11.5): sectores económicos (sin esa "
            "clasificación en los datos de Yahoo Finance de este pipeline) "
            "y plazos/duración de Macaulay (son de renta fija)."
        )
        st.caption(f"Repositorio y documentación completa: {ficha['12_informacion_adicional'].split(': ')[-1]}")
    st.caption(f"⚠️ {ficha['13_observaciones']}")


def _render_ficha_tecnica(
    portfolio_bundle: dict | None, capm_bundle: dict | None, result: FetchResult | None
) -> None:
    """Fichas técnicas de portafolio (Guía de Sustentación Final,
    sección 4: "Ficha técnica del portafolio óptimo (tangente), de
    mínimo riesgo y de mayor rendimiento [...] según la normatividad
    de la Superintendencia Financiera de Colombia [...] Decreto 1242
    de 2013, Circular Básica Jurídica y Anexo 6").

    El Decreto 1242/2013 (Art. 3.1.1.9.8) exige la ficha técnica pero
    delega su contenido exacto a la Circular Básica Jurídica — el
    "Anexo 6" que cita la guía del profesor fue reemplazado desde 2022
    por un nuevo "Anexo 1: Ficha Técnica – Fondos de Inversión
    Colectiva" (la estudiante consiguió y subió ese documento). Esta
    ficha sigue su numeración exacta (secciones 1 a 13); lo que un
    portafolio SIMULADO con fines académicos no puede tener (sociedad
    administradora real, calificadora de riesgo, RNVE, comisiones,
    renta fija) queda N/A con el motivo, tal como el propio Anexo 1
    instruye hacer cuando un campo no aplica."""
    st.header("Ficha técnica del portafolio")
    st.caption(
        "Estructura del Anexo 1 \"Ficha Técnica – Fondos de Inversión "
        "Colectiva\" (Circular Básica Jurídica, Superintendencia "
        "Financiera de Colombia, 2022 — reemplaza al antiguo Anexo 6). "
        "Portafolio SIMULADO con fines académicos: los campos que "
        "requieren una sociedad administradora, calificadora de riesgo "
        "o activos de renta fija reales quedan N/A, siguiendo la propia "
        "instrucción del Anexo."
    )

    if not portfolio_bundle or not portfolio_bundle.get("carteras") or not result:
        st.info(
            "Calcula un portafolio en la sección 'Portafolio v2: Markowitz, "
            "Black-Litterman y rebalanceo' arriba para ver sus fichas técnicas."
        )
        return

    carteras = portfolio_bundle["carteras"]
    col1, col2 = st.columns(2)
    with col1:
        var_conf = st.selectbox("Confianza del VaR (todas las fichas)", options=[0.95, 0.99], key="ficha_var_conf")
    with col2:
        var_capital = st.number_input(
            "Inversión hipotética — 2.4/7 (todas las fichas)", min_value=1.0, value=1000000.0,
            step=100000.0, key="ficha_var_capital",
        )

    obligatorias = [
        ("Tangente (máx. Sharpe)", "tangente", "Maximizar la relación retorno-riesgo (ratio de Sharpe)."),
        ("Mínima varianza (GMV)", "mínimo riesgo", "Minimizar la volatilidad total de la cartera."),
        ("Máximo retorno esperado", "mayor rendimiento", "Maximizar el retorno esperado anual."),
    ]
    fichas_export = {}
    st.markdown("**Fichas obligatorias: tangente, mínimo riesgo y mayor rendimiento**")
    for clave, etiqueta, objetivo in obligatorias:
        if clave not in carteras:
            st.caption(f"Cartera '{clave}' no disponible en este run.")
            continue
        ficha = _build_ficha_dict(etiqueta, carteras[clave], objetivo, portfolio_bundle, capm_bundle, result, var_conf, var_capital)
        with st.expander(f"Ficha técnica — {etiqueta}", expanded=(etiqueta == "tangente")):
            _render_fic_card(etiqueta, ficha)
        fichas_export[etiqueta] = ficha

    otras = [k for k in carteras if k not in {c[0] for c in obligatorias}]
    if otras:
        with st.expander("Ver otra cartera (ej. Black-Litterman, óptimo personal)"):
            cartera_nombre = st.selectbox("Cartera", options=otras, key="ficha_cartera_otra")
            objetivo_otra = "Definida por el usuario (ver sección Portafolio v2)."
            ficha_otra = _build_ficha_dict(
                cartera_nombre, carteras[cartera_nombre], objetivo_otra, portfolio_bundle,
                capm_bundle, result, var_conf, var_capital,
            )
            _render_fic_card(cartera_nombre, ficha_otra)
            fichas_export[cartera_nombre] = ficha_otra

    st.download_button(
        "Descargar las fichas técnicas (JSON)",
        data=json.dumps(fichas_export, indent=2, ensure_ascii=False),
        file_name="fichas_tecnicas_portafolio.json",
        mime="application/json",
        key="ficha_download",
    )


def _render_authenticated_view(conn) -> None:
    st.success(f"Sesión activa como **{st.user.get('name', 'usuario')}**.")
    if st.button("Cerrar sesión"):
        sessions.close_session(conn, st.session_state["session_id"])
        audit.record_auth_event(
            conn,
            user_id=st.session_state["user_id"],
            session_id=st.session_state["session_id"],
            event_type="logout",
            result="success",
            app_version=APP_IDENTITY.version,
        )
        for key in ("session_id", "user_id", "pending_provider"):
            st.session_state.pop(key, None)
        st.logout()

    st.divider()
    collection = _render_ticker_collection()

    st.divider()
    _render_date_frequency_horizon()

    st.divider()
    _render_data_fetch(collection)

    st.divider()
    _render_historical_analysis()

    st.divider()
    _render_forecasting()

    st.divider()
    _render_risk_and_levels()

    st.divider()
    _render_comparison_and_export()

    st.divider()
    portfolio_bundle = _render_portfolio_v2(st.session_state.get("fetch_result"), st.session_state.get("date_config"))

    st.divider()
    capm_bundle = _render_beta_capm_v2(st.session_state.get("fetch_result"), portfolio_bundle)

    st.divider()
    _render_sml_desempeno_v2(
        st.session_state.get("fetch_result"), st.session_state.get("date_config"), portfolio_bundle
    )

    st.divider()
    _render_valuation_v2(capm_bundle)

    st.divider()
    _render_ficha_tecnica(portfolio_bundle, capm_bundle, st.session_state.get("fetch_result"))


def main() -> None:
    conn = _get_shared_connection()

    _render_identity_header()
    _render_execution_policy()
    st.divider()

    if not st.user.is_logged_in:
        _render_access_gate(conn)
        return

    _finalize_login_if_needed(conn)  # puede st.stop() o st.rerun()

    if not _guard(conn):
        return

    _render_authenticated_view(conn)


if __name__ == "__main__":
    main()
