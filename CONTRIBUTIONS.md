# CONTRIBUTIONS.md — Robot Analítico TBS-EIA

⚠️ **Estado: equipo aún sin conformar.** Este archivo es una plantilla
—todo el código base fue generado en sesiones de IA dirigidas por una
sola persona sin equipo asignado todavía (ver `AI_USAGE.md`). La guía
exige 3-4 integrantes con "responsabilidades y contribuciones
verificables por integrante" (punto 88, entregable D9). **Antes de la
entrega, reemplazar cada placeholder de abajo** por el nombre real del
integrante y actualizar `src/config.py::APP_IDENTITY` en consecuencia.

## Cómo se debe llenar esto

La guía es clara (sección 11): "el número de commits no prueba por sí
solo la contribución". Cada integrante debe poder **explicar y
modificar en vivo** el código de sus módulos asignados durante la
defensa individual (punto 150). Repartir los módulos siguientes entre
los 3-4 integrantes reales del equipo, y que cada quien:

1. Lea y entienda a fondo el código de sus módulos.
2. Ejecute las pruebas correspondientes y sepa explicar qué verifican.
3. Sea quien las defienda si el docente hace una comprobación
   aleatoria sobre ese módulo (sección 12.3).

## Matriz de módulos (para asignar)

| Módulo | Archivos | Pruebas | Integrante asignado |
|---|---|---|---|
| Identidad y disclaimer (RF-01) | `src/config.py`, `src/disclaimer.py` | `test_rf01_identity.py` (7) | *(pendiente)* |
| Acceso OIDC y sesión (RF-02) | `src/auth.py`, `src/consent.py`, `src/sessions.py`, `src/audit.py`, `src/notifications.py`, `src/notifications_worker.py`, `src/privacy.py`, `src/db.py` | `test_rf02_infra.py` (12), `test_rf02_login_flow.py` (5) | *(pendiente)* |
| Tickers y configuración (RF-03/RF-04) | `src/tickers.py`, `src/horizon.py` | `test_rf03_tickers.py` (16), `test_rf04_horizon.py` (26) | *(pendiente)* |
| Datos: descarga, limpieza, remuestreo (RF-05 a RF-08) | `src/data.py` | `test_rf05_08_data.py` (41) | *(pendiente)* |
| Análisis histórico (RF-09 a RF-12) | `src/analytics.py` | `test_rf09_12_analytics.py` (37) | *(pendiente)* |
| Forecasting homocedástico (RF-13 a RF-15) | `src/forecasting.py` | `test_rf13_15_forecasting.py` (14) | *(pendiente)* |
| Riesgo y niveles de decisión (RF-16 a RF-18) | `src/risk.py` | `test_rf16_18_risk.py` (24) | *(pendiente)* |
| Comparación y exportación (RF-19 a RF-22) | `src/comparison.py`, `src/export.py` | `test_rf19_21_comparison.py` (15), `test_rf22_export.py` (5) | *(pendiente)* |
| Ciclo de vida (RNF-03) | `src/lifecycle.py` | `test_lifecycle.py` (17) | *(pendiente)* |
| Interfaz Streamlit (todas las vistas) | `app.py` | (integra todos los módulos anteriores) | *(pendiente)* |
| Documentación (README, AI_USAGE, TRACEABILITY, este archivo) | `README.md`, `AI_USAGE.md`, `TRACEABILITY.md`, `CONTRIBUTIONS.md` | Revisión documental (RNF-05) | *(pendiente)* |
| Video de defensa y coordinación general | — | — | *(pendiente)* |

## Registro de commits (llenar con el historial real de Git)

| Integrante | Commit | Descripción |
|Mariana Tobón H|---|---|
| *(pendiente)* |  Repositorio inicial generado con asistencia de IA |

---

**Nota para la defensa:** si el docente pregunta por la distribución
real del trabajo y el equipo respondió con ayuda intensiva de IA para
todo el código (ver `AI_USAGE.md`), la contribución individual
verificable pasa a ser principalmente: qué módulo cada quien entendió,
validó, y puede defender — no quién "escribió" cada línea. Sean
honestos sobre esto; la guía trata el uso intensivo de IA declarado
como aceptable (sección 10), y ocultarlo sí sería falta grave (punto
109, sección 11.1).
