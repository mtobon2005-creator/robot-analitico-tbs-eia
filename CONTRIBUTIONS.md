# CONTRIBUTIONS.md — Botiverso (Robot Analítico TBS-EIA)

**Estado: equipo de 2 integrantes — Mariana Tobón H. y David Torres**
(la guía sugiere 3-4 en el punto 1.1 "Ficha de la actividad"; el
equipo quedó en 2, confirmado con el docente). Todo el código fue
generado en sesiones de IA dirigidas por Mariana Tobón H. (ver
`AI_USAGE.md`); David Torres se incorpora como **coautor de la
totalidad del proyecto**, sin división de módulos entre los dos —
ambos integrantes son responsables de poder explicar, ejecutar y
modificar en vivo **cualquier** módulo durante la defensa individual
(punto 150 de la guía).

## Cómo se debe leer esto (coautoría sin división de módulos)

La guía es clara (sección 11): "el número de commits no prueba por sí
solo la contribución". Este equipo decidió explícitamente NO dividir
el proyecto en módulos por integrante — ambos responden por el todo.
Eso significa que, para **cada** módulo de la tabla siguiente, tanto
Mariana Tobón H. como David Torres deben poder:

1. Leer y entender a fondo el código.
2. Ejecutar las pruebas correspondientes y explicar qué verifican.
3. Defenderlo si el docente hace una comprobación aleatoria sobre ese
   módulo (sección 12.3) — a cualquiera de los dos.

## Matriz de módulos

| Módulo | Archivos | Pruebas | Integrantes responsables |
|---|---|---|---|
| Identidad y disclaimer (RF-01) | `src/config.py`, `src/disclaimer.py` | `test_rf01_identity.py` (7) | Mariana Tobón H., David Torres |
| Acceso OIDC y sesión (RF-02) | `src/auth.py`, `src/consent.py`, `src/sessions.py`, `src/audit.py`, `src/notifications.py`, `src/notifications_worker.py`, `src/privacy.py`, `src/db.py` | `test_rf02_infra.py` (12), `test_rf02_login_flow.py` (5) | Mariana Tobón H., David Torres |
| Tickers y configuración (RF-03/RF-04) | `src/tickers.py`, `src/horizon.py` | `test_rf03_tickers.py` (16), `test_rf04_horizon.py` (26) | Mariana Tobón H., David Torres |
| Datos: descarga, limpieza, remuestreo (RF-05 a RF-08) | `src/data.py` | `test_rf05_08_data.py` (41) | Mariana Tobón H., David Torres |
| Análisis histórico (RF-09 a RF-12) | `src/analytics.py` | `test_rf09_12_analytics.py` (37) | Mariana Tobón H., David Torres |
| Forecasting homocedástico (RF-13 a RF-15) | `src/forecasting.py` | `test_rf13_15_forecasting.py` (14) | Mariana Tobón H., David Torres |
| Riesgo y niveles de decisión (RF-16 a RF-18) | `src/risk.py` | `test_rf16_18_risk.py` (24) | Mariana Tobón H., David Torres |
| Comparación y exportación (RF-19 a RF-22) | `src/comparison.py`, `src/export.py` | `test_rf19_21_comparison.py` (15), `test_rf22_export.py` (5) | Mariana Tobón H., David Torres |
| Ciclo de vida (RNF-03) | `src/lifecycle.py` | `test_lifecycle.py` (17) | Mariana Tobón H., David Torres |
| Escalamiento v2: portafolios (Markowitz, Black-Litterman, rebalanceo, covarianza/correlación) | `src/portfolio.py`, `src/black_litterman.py`, `src/rebalance.py`, `src/covariance.py` | `test_v2_portfolio.py` (20), `test_v2_black_litterman.py`, `test_v2_rebalance.py`, `test_v2_covariance.py` | Mariana Tobón H., David Torres |
| Escalamiento v2: beta/CAPM, valoración, técnico, trazabilidad | `src/beta_capm.py`, `src/valuation.py`, `src/technical.py`, `src/traceability.py` | `test_v2_beta_capm.py`, `test_v2_valuation.py`, `test_v2_technical.py`, `test_v2_traceability.py` | Mariana Tobón H., David Torres |
| Interfaz Streamlit (todas las vistas) | `app.py` | (integra todos los módulos anteriores) | Mariana Tobón H., David Torres |
| Identidad visual y propuesta de valor | `assets/logo_botiverso.svg`, `src/config.py` | N/A (identidad, sin lógica de negocio) | Mariana Tobón H., David Torres |
| Documentación (README, AI_USAGE, TRACEABILITY, este archivo) | `README.md`, `AI_USAGE.md`, `TRACEABILITY.md`, `CONTRIBUTIONS.md` | Revisión documental (RNF-05) | Mariana Tobón H., David Torres |
| Video de defensa y coordinación general | — | — | Mariana Tobón H., David Torres |

## Registro de commits

| Integrante | Commit | Descripción |
|---|---|---|
| Mariana Tobón H. | `125ebb8`/`fc9e64d`/`ef22c2b` | Repositorio inicial (núcleo RF-01 a RF-22) generado con asistencia de IA. |
| Mariana Tobón H. | `8fc636c` | Fix `ImportError` (import muerto en `app.py`) que rompía el despliegue en Streamlit Cloud. |
| Mariana Tobón H. | `0a59212` | Fix regresión v1: `APP_IDENTITY.members` (bug de tupla) y test de sesión única desactualizado. |
| Mariana Tobón H., David Torres | `5c592d9`…`382af31` | Escalamiento v2 completo (segunda entrega): Markowitz, Black-Litterman, rebalanceo, covarianza/correlación, beta/CAPM, valoración, ficha técnica. |
| Mariana Tobón H., David Torres | `5924ab7`/`aa539f8` | Identidad visual "Botiverso": logo, nombre, tagline, propuesta de valor. |

Los commits de la primera entrega (núcleo v1, `125ebb8` a `0a59212`)
fueron dirigidos únicamente por Mariana Tobón H. David Torres se
incorpora al equipo al inicio de la segunda entrega (el escalamiento
v2 que arranca en `5c592d9`). Lo anterior es un registro histórico
honesto, no una atribución retroactiva: no se le adjudican a David
Torres commits anteriores a su incorporación. Desde el escalamiento
v2 en adelante, ambos integrantes son coautores de cualquier cambio
nuevo, se refleje o no el nombre de ambos en el mensaje del commit.

---

**Nota para la defensa:** si el docente pregunta por la distribución
real del trabajo y el equipo respondió con ayuda intensiva de IA para
todo el código (ver `AI_USAGE.md`), la contribución individual
verificable pasa a ser principalmente: qué módulo cada quien entendió,
validó, y puede defender — no quién "escribió" cada línea ni quién
aparece en más commits. Este equipo decidió, además, no dividirse el
proyecto por módulos: ambos integrantes deben poder defender
cualquier parte, sin excusa de "ese módulo no es el mío". Sean
honestos sobre esto; la guía trata el uso intensivo de IA declarado
como aceptable (sección 10), y ocultarlo sí sería falta grave (punto
109, sección 11.1).
