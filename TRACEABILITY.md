# TRACEABILITY.md — Robot Analítico TBS-EIA

Matriz de trazabilidad completa: requisito → dónde vive en el código →
qué prueba lo verifica → qué criterio de rúbrica cubre → qué entregable
lo evidencia. Basada en la sección 8.2 de la guía evaluativa, rellenada
con las rutas reales del repositorio.

**Cómo leer "Pruebas propias":** `archivo::cantidad` es el número de
casos de prueba (items de pytest, incluyendo variantes parametrizadas)
en ese archivo. La cantidad total del proyecto es **221**, todos
pasando (`pytest tests/ -q`).

**Convención de estado:**
- ✅ Implementado y probado (código + tests pasando).
- ⚠️ Implementado con limitación documentada (ver README, sección
  "Limitaciones conocidas").
- ❌ No implementado en este commit.

---

## Núcleo funcional (RF-01 a RF-22)

| RF | Requisito (resumen) | Implementación | Pruebas propias | Pruebas oficiales | Rúbrica | Estado |
|----|---|---|---|---|---|---|
| RF-01 | Identidad, política de ejecución, disclaimer con aceptación expresa | `src/config.py`, `src/disclaimer.py`, `app.py::_render_identity_header`, `_render_execution_policy` | `test_rf01_identity.py` (7) | T-18, T-25 | G1, G8 | ✅ |
| RF-02 | Acceso OIDC Google/Microsoft, bloqueo servidor, sesión lógica, perfil por (iss,sub) | `src/auth.py`, `src/consent.py`, `src/sessions.py`, `src/audit.py`, `src/notifications.py`, `src/notifications_worker.py`, `src/privacy.py`, `app.py::_render_access_gate`, `_finalize_login_if_needed`, `_guard` | `test_rf02_infra.py` (12), `test_rf02_login_flow.py` (5, integración) | T-18 a T-24 | G10 | ⚠️ (ver limitación #1 del README: cookie HttpOnly del preconsentimiento) |
| RF-03 | Colección dinámica de tickers, 1 activo o ≥20 válidos simultáneos | `src/tickers.py`, `app.py::_render_ticker_collection` | `test_rf03_tickers.py` (16) | T-04 a T-06 | G2, G7 | ✅ |
| RF-04 | Fechas, frecuencia, horizonte H libre (periodos o fecha objetivo) | `src/horizon.py`, `app.py::_render_date_frequency_horizon` | `test_rf04_horizon.py` (26) | T-07 a T-10 | G5, G8 | ⚠️ (ver limitación #2: conversión fecha→periodos es aproximación de calendario) |
| RF-05 | Descarga de precios con proveedor/moneda/zona horaria/fecha identificados | `src/data.py` (`FixtureProvider`, `MockProvider`, `YFinanceProvider`), `app.py::_render_data_fetch` | `test_rf05_08_data.py` (41, cubre RF-05 a RF-08) | T-03 | G2 | ⚠️ (`YFinanceProvider` sin probar contra red real) |
| RF-06 | Ordenar, deduplicar, tratar faltantes, rechazar precios no positivos | `src/data.py::clean_prices` | incluido en `test_rf05_08_data.py` | T-01 a T-03 | G2 | ✅ |
| RF-07 | Remuestrear antes de calcular rendimientos | `src/data.py::resample_prices` | incluido en `test_rf05_08_data.py` — verificado exacto contra RESAMPLE-01 (109 semanales / 26 mensuales, AAPL) | T-01, T-07 | G2, G3 | ✅ |
| RF-08 | Validar ticker inexistente/vacío/timeout/insuficiente sin detener los demás | `src/data.py::fetch_and_clean_many` | incluido en `test_rf05_08_data.py` — verificado exacto contra T-06/FAIL-20P1-01 (20 válidos + `EIA_INVALID_2026`) | T-03, T-06 | G2 | ✅ |
| RF-09 | Gráficos precio/rendimiento vs. tiempo con título, ticker, unidad, frecuencia, fechas, fuente | `app.py::_render_historical_analysis` | visual (Streamlit); datos subyacentes cubiertos por `test_rf09_12_analytics.py` (37) | T-04, T-25 | G3, G8 | ✅ |
| RF-10 | Rendimiento exclusivamente logarítmico | `src/analytics.py::compute_log_returns` | verificado exacto contra LOG-01 (100,110,99 → g=[0.0953...,-0.1054...]) | T-01, T-07 | G3 | ✅ |
| RF-11 | Estadísticas descriptivas anualizadas | `src/analytics.py::descriptive_stats`, `quantile_type7` | verificado exacto contra STAT-01, FREQ-01, y los **20 tickers oficiales** de `Resultados_esperados_20_activos_TBS_EIA.csv` | T-01, T-07 | G3, G4, G6 | ✅ |
| RF-12 | Último precio/fecha, drawdown, percentil midrank, ventana reciente vs. completa | `src/analytics.py::compute_drawdown_series`, `build_present_context`, `compare_full_vs_recent_window` | incluido en `test_rf09_12_analytics.py` | T-04, T-12 | G3, G4 | ✅ |
| RF-13 | Modelo A (caminata aleatoria) y Modelo B (lognormal con deriva), homocedásticos | `src/forecasting.py::horizon_params` | verificado exacto contra MODEL-A-01, MODEL-B-01 | T-11 | G5 | ✅ |
| RF-14 | Trayectoria analítica completa 1..H y distribución terminal | `src/forecasting.py::generate_trajectory`, `app.py::_render_forecasting` | verificado exacto contra PATH-B-01 (h=1,2,3) | T-08, T-09, T-11 | G5 | ✅ |
| RF-15 | Walk-forward: ventana expansiva, 10 orígenes, MAE/RMSE, cobertura 90%, dirección | `src/forecasting.py::validate_walk_forward` | verificado exacto contra WF-01 (AAPL real, ambos modelos, MAE/RMSE/cobertura/dirección) | T-11 | G5 | ✅ |
| RF-16 | VaR paramétrico individual 95%/99% | `src/risk.py::compute_var` | verificado exacto contra VAR99-A-01, VAR99-B-01, y el caso "serie constante" (VaR=0) | T-15 | G6 | ✅ |
| RF-17 | Entrada, SL_H, TP_H, precio de equilibrio, costos | `src/risk.py::evaluate_signal`, `equilibrium_price` | verificado exacto contra COST-B-01 | T-14 | G6 | ✅ |
| RF-18 | Probabilidades terminales ganar/perder/neutral, no señal reproducible | `src/risk.py::evaluate_signal` (rama continua y determinista) | verificado exacto contra COST-B-01 (prob_win=0.7905...) y caso serie constante (neutral=100%) | T-13, T-14 | G6 | ✅ |
| RF-19 | Tabla comparable + mapa histórico, mínimo 20 simultáneos | `src/comparison.py::build_comparison_table`, `app.py::_render_comparison_and_export` | `test_rf19_21_comparison.py` (15) — verificado con los 20 tickers oficiales | T-05, T-16 | G7 | ✅ |
| RF-20 | Etiquetado, dominancia, fechas comunes, bloqueo de monedas incompatibles | `src/comparison.py::dominates`, `compute_non_dominated`, `_check_currency_compatibility`, `_common_date_index` | verificado exacto: las 20 filas `non_dominated` del archivo oficial coinciden una por una | T-16 | G7 | ✅ |
| RF-21 | Regla de preselección explícita (4 variantes), sin implicar frontera eficiente | `src/comparison.py::select_max_mean_under_risk_limit`, `select_min_volatility_under_mean_floor`, `select_max_rvr`, `select_non_dominated_set` | verificado exacto: `select_max_rvr` identifica PG, igual que la columna oficial `selected_max_rvr` | T-17 | G7 | ✅ |
| RF-22 | Exportar precios, resultados, tabla comparativa y parámetros (CSV/JSON, con fecha y fuente) | `src/export.py`, `app.py::_render_comparison_and_export`, `_render_risk_and_levels` (botones de descarga) | `test_rf22_export.py` (7) | T-04, T-05 | G7, G8, G11 | ✅ |

## Requisitos no funcionales (RNF-01 a RNF-05)

| RNF | Requisito (resumen) | Implementación | Estado |
|-----|---|---|---|
| RNF-01 | Usabilidad y accesibilidad (teclado, contraste, alt text, alternativa tabular) | Avatar con `role='img' aria-label=...`; **cada gráfico** (precio, rendimiento, drawdown, trayectoria de forecasting, mapa comparativo) tiene un expander con `st.dataframe` como alternativa tabular; jerarquía de encabezados corregida (`st.header` en vez de `st.subheader`, evita saltar de h1 a h3); navegación por teclado y foco visible heredados de los widgets nativos de Streamlit | ✅ **Auditado con Lighthouse (Chrome DevTools): 98/100 en Accessibility.** El único hallazgo (encabezados no secuenciales) ya se corrigió. |
| RNF-02 | Arquitectura monolítica modular, configuración externa, dependencias fijadas, URL HTTPS | `requirements.txt` (versiones fijadas), `.streamlit/secrets.toml.example`, `.gitignore`, estructura `src/` modular por responsabilidad | ✅ (falta el despliegue real con URL HTTPS — pendiente de la cuenta de hosting del curso) |
| RNF-03 | OIDC mantenido, allowlist, preconsentimiento, sesión lógica, transacción, outbox/worker, mínimo privilegio, retención y purga | `src/auth.py`, `src/consent.py`, `src/sessions.py`, `src/notifications_worker.py`, `src/lifecycle.py` | ⚠️ (ver limitaciones #1 y #4 del README) |
| RNF-04 | Pruebas y reproducibilidad: fixtures sin internet, mocks, tolerancias, cobertura, commit reproducible | `tests/fixtures/` (fixtures oficiales verificados por SHA256SUMS.txt), `MockProvider`, tolerancias `pytest.approx(abs=1e-8)` en todo el proyecto | ✅ (221/221 pruebas, 0 dependencias de red) |
| RNF-05 | IA, autoría y documentación: README, AI_USAGE, CONTRIBUTIONS, TRACEABILITY, licencias, referencias APA 7 | Este archivo, `AI_USAGE.md`, `CONTRIBUTIONS.md`, `README.md` (sección Referencias), `LICENSE` | ✅ |

### RNF-01 — Revisión manual de accesibilidad (checklist de Lighthouse)

Lighthouse marca 10 puntos como "revisar manualmente" porque no puede
verificarlos automáticamente. Revisados uno por uno el 17-sep-2026:

| Punto | Estado | Nota |
|---|---|---|
| Controles interactivos enfocables por teclado | ✅ | Todos son widgets nativos de Streamlit (botones, checkboxes, radios, selects) — enfocables por defecto del navegador. |
| Elementos interactivos indican su propósito/estado | ✅ | Cada widget tiene etiqueta de texto visible; los deshabilitados (`disabled=...`) lo muestran visualmente. |
| Orden de tabulación lógico | ✅ | No se usa CSS que reordene el layout — sigue el orden del código. |
| Orden visual = orden del DOM | ✅ | Mismo motivo — sin posicionamiento absoluto ni `z-index` manual. |
| El foco no queda atrapado en una región | ✅ | No hay modales ni `st.dialog` con trampa de foco en la app. |
| El foco se dirige a contenido nuevo agregado a la página | ⚠️ | Al abrir un `st.expander` (ej. "Ver datos en tabla"), el foco de teclado no salta automáticamente al contenido revelado. Es una limitación conocida del framework Streamlit, no algo controlable desde el código de la app. |
| Se usan landmarks HTML5 para navegación | ✅ | Provistos por la plantilla base de Streamlit (`<main>`, etc.), no sobreescritos. |
| Contenido offscreen oculto a tecnología asistiva | N/A | La app no oculta contenido a propósito fuera de pantalla. |
| Controles personalizados tienen etiquetas asociadas | ✅ | El único elemento no-nativo es el avatar (`role='img' aria-label=...`); el `st.iframe` invisible (cookie técnica de sesión) no tiene contenido interactivo, por lo que no aplica etiqueta. |
| Controles personalizados tienen roles ARIA | ✅ | Mismo caso — avatar con `role='img'` ya declarado. |

Conclusión: 9/10 puntos verificados sin hallazgos; 1 limitación
documentada (foco no dirigido a expanders nuevos) que es inherente al
framework, no un descuido del código de la app.

---

## Resumen de limitaciones conocidas (ver también README.md)

1. **Cookie HttpOnly del preconsentimiento** (`src/consent.py`) — se usa
   `st.session_state` en lugar de una cookie propia Secure/HttpOnly/
   SameSite=Lax literal, por restricción del modelo de script de
   Streamlit. Afecta potencialmente G10.2.
2. **Conversión fecha objetivo → periodos** (`src/horizon.py`) — es una
   aproximación de calendario (días hábiles/semanas/meses), no cuenta
   contra el índice real de fechas remuestreadas.
3. **`YFinanceProvider`** (`src/data.py`) — implementado pero sin
   probar contra la red real (entorno de desarrollo sin acceso a
   Yahoo Finance).
4. **Purga de logs/respaldos de infraestructura** (`src/lifecycle.py`)
   — depende de configuración externa (hosting/backups que el curso
   provee, punto 46 de la guía); el worker purga lo que vive en su
   propia base de datos, no la infraestructura subyacente.
5. ~~**RNF-01 (accesibilidad)**~~ — **resuelto.** Auditado con
   Lighthouse: 98/100 en Accessibility. El único hallazgo (jerarquía
   de encabezados no secuencial) ya se corrigió.

Estas limitaciones deben discutirse explícitamente durante la defensa
individual (sección 12.3 de la guía) — declararlas y poder explicarlas
es parte de lo que la rúbrica evalúa favorablemente (12.4: "error
técnico sin engaño... no constituye fraude").
