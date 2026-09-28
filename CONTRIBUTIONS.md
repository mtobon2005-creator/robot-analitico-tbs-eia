# CONTRIBUTIONS.md — Robot Analítico TBS-EIA

**Estado: equipo de 1 integrante, confirmado con el docente** (la guía
sugiere 3-4 en el punto 1.1 "Ficha de la actividad", pero para este
piloto se acordó trabajar en solitario — ver mandato v2 en `README.md`).
Todo el código fue generado en sesiones de IA dirigidas por Mariana
Tobón H. (ver `AI_USAGE.md`). Como no hay otros integrantes, no aplica
repartir módulos entre personas distintas: la responsabilidad de poder
explicar y modificar en vivo cualquier módulo durante la defensa
individual (punto 150) recae completa en la única integrante.

## Cómo se debe leer esto (equipo de 1)

La guía es clara (sección 11): "el número de commits no prueba por sí
solo la contribución". Con un solo integrante no hay módulos que
repartir entre personas, pero la exigencia de la defensa individual
(punto 150) no cambia: Mariana Tobón H. debe poder, para **cualquier**
módulo de la tabla siguiente:

1. Leer y entender a fondo el código.
2. Ejecutar las pruebas correspondientes y explicar qué verifican.
3. Defenderlo si el docente hace una comprobación aleatoria sobre ese
   módulo (sección 12.3).

## Matriz de módulos

| Módulo | Archivos | Pruebas | Integrante |
|---|---|---|---|
| Identidad y disclaimer (RF-01) | `src/config.py`, `src/disclaimer.py` | `test_rf01_identity.py` (7) | Mariana Tobón H. |
| Acceso OIDC y sesión (RF-02) | `src/auth.py`, `src/consent.py`, `src/sessions.py`, `src/audit.py`, `src/notifications.py`, `src/notifications_worker.py`, `src/privacy.py`, `src/db.py` | `test_rf02_infra.py` (12), `test_rf02_login_flow.py` (5) | Mariana Tobón H. |
| Tickers y configuración (RF-03/RF-04) | `src/tickers.py`, `src/horizon.py` | `test_rf03_tickers.py` (16), `test_rf04_horizon.py` (26) | Mariana Tobón H. |
| Datos: descarga, limpieza, remuestreo (RF-05 a RF-08) | `src/data.py` | `test_rf05_08_data.py` (41) | Mariana Tobón H. |
| Análisis histórico (RF-09 a RF-12) | `src/analytics.py` | `test_rf09_12_analytics.py` (37) | Mariana Tobón H. |
| Forecasting homocedástico (RF-13 a RF-15) | `src/forecasting.py` | `test_rf13_15_forecasting.py` (14) | Mariana Tobón H. |
| Riesgo y niveles de decisión (RF-16 a RF-18) | `src/risk.py` | `test_rf16_18_risk.py` (24) | Mariana Tobón H. |
| Comparación y exportación (RF-19 a RF-22) | `src/comparison.py`, `src/export.py` | `test_rf19_21_comparison.py` (15), `test_rf22_export.py` (5) | Mariana Tobón H. |
| Ciclo de vida (RNF-03) | `src/lifecycle.py` | `test_lifecycle.py` (17) | Mariana Tobón H. |
| Interfaz Streamlit (todas las vistas) | `app.py` | (integra todos los módulos anteriores) | Mariana Tobón H. |
| Documentación (README, AI_USAGE, TRACEABILITY, este archivo) | `README.md`, `AI_USAGE.md`, `TRACEABILITY.md`, `CONTRIBUTIONS.md` | Revisión documental (RNF-05) | Mariana Tobón H. |
| Video de defensa y coordinación general | — | — | Mariana Tobón H. |

## Registro de commits

| Integrante | Commit | Descripción |
|---|---|---|
| Mariana Tobón H. | `125ebb8`/`fc9e64d`/`ef22c2b` | Repositorio inicial (núcleo RF-01 a RF-22) generado con asistencia de IA. |
| Mariana Tobón H. | `8fc636c` | Fix `ImportError` (import muerto en `app.py`) que rompía el despliegue en Streamlit Cloud. |
| Mariana Tobón H. | `0a59212` | Fix regresión v1: `APP_IDENTITY.members` (bug de tupla) y test de sesión única desactualizado. |

---

**Nota para la defensa:** si el docente pregunta por la distribución
real del trabajo y el equipo respondió con ayuda intensiva de IA para
todo el código (ver `AI_USAGE.md`), la contribución individual
verificable pasa a ser principalmente: qué módulo cada quien entendió,
validó, y puede defender — no quién "escribió" cada línea. Sean
honestos sobre esto; la guía trata el uso intensivo de IA declarado
como aceptable (sección 10), y ocultarlo sí sería falta grave (punto
109, sección 11.1).
