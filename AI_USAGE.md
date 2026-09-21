# AI_USAGE.md — Robot Analítico TBS-EIA

Registro de uso de inteligencia artificial generativa en este proyecto,
conforme a la sección 10 de la guía evaluativa. Todo el código de este
repositorio fue producido en sesiones de trabajo con Claude (Anthropic)
dentro de Claude.ai, dirigidas módulo por módulo por el equipo. Este
archivo documenta cada interacción sustantiva: qué se pidió, qué
produjo la IA, y qué falta por validar humanamente.

**Nota de honestidad importante para la defensa (sección 10.2 de la
guía):** el uso de IA en este proyecto fue **intensivo y de alcance
completo** — no interacciones puntuales de autocompletado, sino la
construcción módulo por módulo de todo el código, las pruebas y esta
documentación. Esto es explícitamente permitido y esperado por la
guía ("Uso de IA: Permitido y esperado, con trazabilidad, validación
humana y defensa del conocimiento"), **siempre que el equipo pueda
explicar, ejecutar y modificar cada parte durante la defensa
individual** (puntos 108 y 110 de la sección 11.1). La responsabilidad
matemática, financiera, técnica, jurídica y ética sigue siendo del
equipo (sección 10, párrafo introductorio).

---

## Sesión 1 — RF-01 (identidad y disclaimer)

| Campo | Detalle |
|---|---|
| Fecha y responsable | 14 sep 2026 · Mariana Tobón H |
| Herramienta y modelo | Claude (Anthropic), vía Claude.ai |
| Propósito | Construir el esqueleto del repositorio y el módulo de identidad/disclaimer desde cero |
| Prompt (resumen) | "Empecemos de 0" tras compartir la guía evaluativa y los fixtures oficiales; se acordó Streamlit como framework por su soporte nativo de OIDC (`st.login`) |
| Archivo o función | `requirements.txt`, `src/config.py`, `src/disclaimer.py`, `app.py` (versión inicial), `tests/unit/test_rf01_identity.py` |
| Cambios humanos | Ninguno aún — pendiente de revisión por el equipo |
| Validación | 7/7 pruebas automatizadas pasando (`pytest tests/unit/test_rf01_identity.py`) |
| Limitaciones | Identidad del equipo en `src/config.py` usa placeholders — deben reemplazarse con los datos reales del equipo |

## Sesión 2 — RF-02 (acceso OIDC, sesión, auditoría, notificaciones)

| Campo | Detalle |
|---|---|
| Fecha y responsable | 14 sep 2026 · Mariana Tobon H |
| Herramienta y modelo | Claude (Anthropic), vía Claude.ai |
| Propósito | Implementar autenticación OIDC real (Google/Microsoft), preconsentimiento, sesión lógica, auditoría inmutable y outbox de notificación |
| Prompt (resumen) | "Vale, vamos con RF-02" — se pidió dividir en piezas: base de datos, preconsentimiento, auth/sesión, auditoría, notificaciones |
| Archivo o función | `migrations/001_init.sql`, `src/db.py`, `src/consent.py`, `src/sessions.py`, `src/audit.py`, `src/notifications.py`, `src/notifications_worker.py`, `src/auth.py`, `src/privacy.py`, `.streamlit/secrets.toml.example` |
| Cambios humanos | Ninguno aún |
| Validación | 12 pruebas unitarias + 5 de integración (transacción atómica, allowlist, identidad incompleta) — todas pasando |
| Limitaciones | **Declarada explícitamente en el código y el README**: la cookie HttpOnly del preconsentimiento no es 100% nativa en Streamlit puro; se usa `st.session_state` como equivalente más cercano. Discutir con el docente. |

## Sesión 3 — RF-03 y RF-04 (tickers, fechas, frecuencia, horizonte)

| Campo | Detalle |
|---|---|
| Fecha y responsable | 14 sep 2026 · Mariana Tobón H |
| Herramienta y modelo | Claude (Anthropic), vía Claude.ai |
| Propósito | Colección dinámica de tickers y configuración de fechas/frecuencia/horizonte H libre |
| Prompt (resumen) | "va rf-04" tras completar RF-03 en el turno anterior |
| Archivo o función | `src/tickers.py`, `src/horizon.py`, secciones correspondientes de `app.py` |
| Cambios humanos | Ninguno aún |
| Validación | 16 + 26 pruebas unitarias, incluyendo el caso oficial `EIA_INVALID_2026` del fixture y validación de que H no se limita a botones predefinidos |
| Limitaciones | La conversión "fecha objetivo → periodos" en `src/horizon.py` es una aproximación de calendario, no cuenta contra el índice real de fechas remuestreadas (se corrige conceptualmente en RF-14) |

## Sesión 4 — RF-05 a RF-08 (descarga, limpieza, remuestreo, calidad)

| Campo | Detalle |
|---|---|
| Fecha y responsable | 15 sep 2026 · Mariana Tobón H |
| Herramienta y modelo | Claude (Anthropic), vía Claude.ai |
| Propósito | Proveedor de datos (fixture + mock + yfinance), limpieza de precios, remuestreo antes de rendimientos, aislamiento de fallos parciales |
| Prompt (resumen) | Continuación secuencial del plan RF por RF |
| Archivo o función | `src/data.py` completo |
| Cambios humanos | Ninguno aún |
| Validación | 41 pruebas; remuestreo semanal/mensual verificado numéricamente contra la matriz oficial (RESAMPLE-01: 109/26 observaciones para AAPL); fallo parcial verificado contra T-06 con los 20 tickers reales + `EIA_INVALID_2026` |
| Limitaciones | `YFinanceProvider` implementado pero sin probar contra la red real (el entorno de desarrollo no tenía acceso a Yahoo Finance) |

## Sesión 5 — RF-09 a RF-12 (análisis histórico)

| Campo | Detalle |
|---|---|
| Fecha y responsable | 15 sep 2026 · Mariana Tobón H |
| Herramienta y modelo | Claude (Anthropic), vía Claude.ai |
| Propósito | Rendimientos logarítmicos, estadísticas descriptivas anualizadas, drawdown, percentil midrank |
| Prompt (resumen) | Continuación secuencial |
| Archivo o función | `src/analytics.py` completo |
| Cambios humanos | Ninguno aún |
| Validación | 37 pruebas. **Verificación exacta**: los 20 tickers oficiales del fixture procesados de punta a punta (descarga→limpieza→rendimientos→estadísticas→cuantiles→drawdown) coinciden con `Resultados_esperados_20_activos_TBS_EIA.csv` hasta 1e-8 |
| Limitaciones | Ninguna adicional a las ya declaradas |

## Sesión 6 — RF-13 a RF-15 (forecasting homocedástico, walk-forward)

| Campo | Detalle |
|---|---|
| Fecha y responsable | 15 sep 2026 · Mariana Tobón H |
| Herramienta y modelo | Claude (Anthropic), vía Claude.ai |
| Propósito | Modelo A/B homocedásticos, trayectoria analítica 1..H, validación walk-forward de 10 orígenes |
| Prompt (resumen) | Continuación secuencial |
| Archivo o función | `src/forecasting.py` completo |
| Cambios humanos | Ninguno aún |
| Validación | 14 pruebas. **Verificación exacta** contra MODEL-A-01, MODEL-B-01, PATH-B-01, y WF-01 (walk-forward completo con AAPL real, ambos modelos: MAE, RMSE, cobertura y exactitud direccional coinciden) |
| Limitaciones | Ninguna adicional |

## Sesión 7 — RF-16 a RF-18 (VaR, niveles, probabilidades)

| Campo | Detalle |
|---|---|
| Fecha y responsable | 16 sep 2026 · Mariana Tobón H |
| Herramienta y modelo | Claude (Anthropic), vía Claude.ai |
| Propósito | VaR paramétrico, stop-loss/take-profit con costos, precio de equilibrio, probabilidades terminales |
| Prompt (resumen) | Continuación secuencial |
| Archivo o función | `src/risk.py` completo |
| Cambios humanos | Ninguno aún |
| Validación | 24 pruebas. Verificación exacta contra VAR99-A-01, VAR99-B-01, COST-B-01 y el caso "serie constante" |
| Limitaciones | Ninguna adicional |

## Sesión 8 — RF-19 a RF-22 (comparación, dominancia, exportación)

| Campo | Detalle |
|---|---|
| Fecha y responsable | 16 sep 2026 · Mariana Tobón H |
| Herramienta y modelo | Claude (Anthropic), vía Claude.ai |
| Propósito | Mapa histórico rendimiento-riesgo, dominancia, 4 reglas de preselección, exportación CSV/JSON |
| Prompt (resumen) | Continuación secuencial |
| Archivo o función | `src/comparison.py`, `src/export.py` completos |
| Cambios humanos | Ninguno aún |
| Validación | 15 + 5 pruebas. **Verificación exacta**: las 20 filas `non_dominated` y la fila `selected_max_rvr` del archivo oficial coinciden una por una con la implementación |
| Limitaciones | La exportación cubre precios y tabla comparativa; falta un botón dedicado para exportar VaR/niveles/forecasting por activo individual |

## Sesión 9 — Ciclo de vida (lifecycle_worker, RNF-03)

| Campo | Detalle |
|---|---|
| Fecha y responsable | 16 sep 2026 · Mariana Tobón H |
| Herramienta y modelo | Claude (Anthropic), vía Claude.ai |
| Propósito | Revocación inmediata, purga programada al cierre del curso, worker periódico, deletion markers sin PII |
| Prompt (resumen) | "Yo iría por el lifecycle_worker primero" (decisión conjunta sobre el orden de trabajo restante) |
| Archivo o función | `src/lifecycle.py` completo |
| Cambios humanos | Ninguno aún |
| Validación | 17 pruebas, incluyendo el caso T-23 (reaplicar purga tras "restaurar" un perfil con `purge_at` vencido) y verificación de que el `deletion_marker` nunca contiene el identificador crudo |
| Limitaciones | La purga de logs de infraestructura y vencimiento de respaldos depende de configuración externa que el curso provee (no está bajo control directo de este código) |

## Sesión 10 — Documentación de cierre

| Campo | Detalle |
|---|---|
| Fecha y responsable | 16 sep 2026 · Mariana Tobón H |
| Herramienta y modelo | Claude (Anthropic), vía Claude.ai |
| Propósito | TRACEABILITY.md, AI_USAGE.md (este archivo), CONTRIBUTIONS.md |
| Prompt (resumen) | "sigamos" tras completar el núcleo funcional y el lifecycle_worker |
| Archivo o función | `TRACEABILITY.md`, `AI_USAGE.md`, `CONTRIBUTIONS.md` |
| Cambios humanos | Ninguno aún |
| Validación | Revisión cruzada manual contra la sección 8.2 de la guía (matriz oficial RF-prueba-rúbrica-entregable) |
| Limitaciones | Las fechas de "Fecha y responsable" son aproximadas (sesiones de una conversación continua); deben ajustarse a los commits reales una vez el equipo tome posesión del repositorio |

---

## Obligaciones pendientes del equipo (sección 10.2 de la guía)

Antes de la entrega, cada integrante debe, para los módulos que le
correspondan según `CONTRIBUTIONS.md`:

1. **Comprender, revisar y probar** cada función incorporada — no
   basta con que las pruebas automatizadas pasen; cada integrante debe
   poder explicar el código en la defensa individual (punto 101).
2. **Contrastar las fórmulas contra bibliografía** — este proyecto ya
   verificó cada fórmula numéricamente contra los fixtures oficiales
   del curso, pero eso no reemplaza entender de dónde sale cada
   ecuación (sección 5 de la guía, punto 102).
3. **Registrar cualquier interacción adicional con IA** que el equipo
   haga a partir de este punto (correcciones, nuevas funcionalidades,
   depuración) siguiendo el mismo formato de tabla de este archivo.
4. **Nunca usar IA durante la defensa individual** (punto 110).
