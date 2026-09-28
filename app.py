"""Robot Analítico TBS-EIA — punto de entrada y navegación.

Alcance de este commit: RF-01 (identidad, disclaimer) + RF-02 (acceso
OIDC Google/Microsoft, sesión lógica, guard servidor, perfiles,
consentimientos, auditoría, outbox de notificación).

Pendiente: RF-03 en adelante (tickers, fechas, analítica, forecasting,
VaR, comparación, exportación) y el lifecycle_worker de purga.
"""
import sys
import os

# Agrega la carpeta raíz al PATH de Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Ahora realiza tus imports normales
import streamlit as st
import altair as alt
import numpy as np
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

from src import auth, sessions, audit
from src.black_litterman import BlackLittermanError, black_litterman
from src.portfolio import (
    PortfolioOptimizationError,
    efficient_frontier,
    global_min_variance,
    max_expected_return,
    personal_optimum,
    tangency_portfolio,
)
from src.rebalance import RebalanceError, rebalance
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
    DuplicateTicker,
    InvalidTicker,
    TickerNotFound,
    add_ticker,
    is_ready_for_comparison,
    is_ready_for_single_asset,
    missing_for_comparison,
    remove_ticker,
)

st.set_page_config(
    page_title=APP_IDENTITY.system_name,
    page_icon="📊",
    layout="wide",
)


@st.cache_resource
def _get_shared_connection():
    conn = get_connection()
    init_schema(conn)
    return conn


def _render_identity_header() -> None:
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


_FLOW_COOKIE_NAME = "tbs_flow_id"


def _start_login(conn, provider: str) -> None:
    """Emite el preconsent_flow y lo guarda en una COOKIE REAL del
    navegador (no en st.session_state).

    Motivo (limitación descubierta y documentada): el redirect a
    Google/Microsoft es una recarga completa de página del navegador,
    no una actualización interna de Streamlit. st.session_state NO
    sobrevive ese viaje de ida y vuelta (queda vacío al regresar),
    aunque st.user.is_logged_in sí se restaura correctamente (usa su
    propio mecanismo de cookie firmada). Una cookie de navegador
    corriente, en cambio, si sobrevive la recarga completa — por eso
    la usamos aquí en vez de session_state."""
    flow_id = issue_preconsent_flow(
        conn, disclaimer_version=DISCLAIMER_VERSION, privacy_version=PRIVACY_NOTICE_VERSION
    )
    st.iframe(
        f"<script>document.cookie = '{_FLOW_COOKIE_NAME}={flow_id}; "
        "path=/; max-age=900; SameSite=Lax';</script>",
        height=1,
    )
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

    iss = claims.get("iss", "")
    provider = "microsoft" if "microsoftonline" in iss else "google"
    flow_id = st.context.cookies.get(_FLOW_COOKIE_NAME)

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
        # Expira la cookie del flow (ya se consumió en la BD; esto es
        # solo higiene, evita dejarla viva innecesariamente).
        st.iframe(
            f"<script>document.cookie = '{_FLOW_COOKIE_NAME}=; path=/; max-age=0';</script>",
            height=1,
        )
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
        col_input, col_btn = st.columns([4, 1])
        with col_input:
            raw_ticker = st.text_input(
                "Agregar ticker", placeholder="Ej: AAPL, BRK.B, TD.TO", label_visibility="collapsed"
            )
        with col_btn:
            submitted = st.form_submit_button("Agregar", use_container_width=True)

    if submitted and raw_ticker:
        try:
            st.session_state["ticker_collection"] = add_ticker(collection, raw_ticker)
            st.rerun()
        except (InvalidTicker, DuplicateTicker) as exc:
            st.error(str(exc))

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


def _render_portfolio_v2(result: FetchResult | None, date_config: dict | None) -> None:
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
    if len(currencies) > 1:
        st.error(
            f"Los activos seleccionados tienen monedas distintas ({', '.join(sorted(currencies))}). "
            "El mandato v2 exige conversión FX explícita (README, Mandato v2 — "
            "aún no implementada); selecciona activos en una sola moneda."
        )
        return

    price_df = pd.DataFrame({t: result.ok[t].prices for t in selected})
    simple_returns = price_df.pct_change(fill_method=None)
    common_mask = simple_returns.notna().all(axis=1)
    simple_returns = simple_returns.loc[common_mask]
    n_obs = len(simple_returns)
    if n_obs < 30:
        st.warning(
            f"Solo {n_obs} observaciones comunes tras alinear fechas — "
            "insuficiente para estimar Sigma con confianza (GUIA_V2, P37/P38)."
        )
        return

    frequency = date_config["frecuencia"]
    m = FRECUENCIAS[frequency]
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
    st.dataframe(carteras_rows, use_container_width=True, hide_index=True)
    st.caption(
        "GMV depende solo de Σ, no de μ (GUIA_V2, tabla 5.1). El óptimo "
        "personal requiere γ del inversionista — no se infiere de los "
        "precios históricos (P57)."
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
        st.altair_chart(line + markers + labels, use_container_width=True)
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

    precios_actuales = np.array([float(result.ok[t].prices.iloc[-1]) for t in selected])

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
    _render_portfolio_v2(st.session_state.get("fetch_result"), st.session_state.get("date_config"))

    st.divider()
    st.header("Núcleo obligatorio: RF-01 a RF-22 completos")
    st.write(
        "Falta cerrar la infraestructura no cubierta por la interfaz "
        "(lifecycle_worker de purga, RNF-01 a RNF-05) y la documentación "
        "final (README completo, AI_USAGE.md, CONTRIBUTIONS.md, "
        "TRACEABILITY.md, video de defensa)."
    )


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
