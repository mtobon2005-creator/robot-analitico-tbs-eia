# CHANGELOG.md — Botiverso

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Las fechas son las del commit real (`git log --date=short`), no
estimaciones.

## [0.2.1] — 2026-11-01 a 2026-11-04 — Gaps de la versión final + sustentación

### Agregado
- Matriz de correlación en vivo, derivada de la misma Σ de Markowitz.
- Beta frente a un índice de mercado o al portafolio óptimo calculado
  (antes solo entre dos activos descargados).
- Valoración CAPM→patrimonio generalizada (ya no atada al caso
  "Alimentos del Norte"), con beta sectorial externo opcional (ej.
  Damodaran, ingresado a mano).
- Ficha técnica consolidada por portafolio, exportable a JSON.
- Línea del Mercado de Capitales (CML) sobre la frontera eficiente.
- Línea del Mercado de Títulos (SML): beta, R² y rendimiento requerido
  CAPM para todos los activos descargados, con descomposición de
  riesgo sistemático/no sistemático.
- Desempeño vs. benchmark: Treynor, alfa de Jensen, Information Ratio
  (además del Sharpe ya existente).
- Ficha técnica reconstruida en formato FIC (Decreto 1242/2013): las
  tres carteras obligatorias (tangente, mínimo riesgo, mayor
  rendimiento) con objetivo, restricciones, pesos y la advertencia
  regulatoria del Art. 3.1.1.9.3.
- Identidad visual "Botiverso": logo, tagline "Explora. Compara.
  Decide.", propuesta de valor.
- `docs/ficha_producto.md` y `docs/matriz_evolucion.md` para la
  sustentación final.
- Este archivo y `.github/workflows/tests.yml` (CI).

### Corregido
- El logo no se veía en producción (solo el texto) — SVG crudo
  incrustado sin width/height caía al tamaño por defecto del
  navegador; cambiado a `st.image()`.

### Eliminado
- Sección de valoración atada al caso "Alimentos del Norte" en la app
  en vivo (quedó solo como material de presentación aparte, hasta
  reconstruirse generalizada).

## [0.1.x] — 2026-09-28 a 2026-10-19 — Escalamiento v2: portafolios

### Agregado
- David Torres se incorpora al equipo (coautoría sin división de
  módulos) — segunda entrega.
- Optimización de portafolio N activos: mínima varianza, tangente,
  óptimo personal, máximo retorno, frontera eficiente
  (`src/portfolio.py`).
- Black-Litterman (prior, views, posterior) validado contra caso de
  control.
- Rebalanceo simulado con costos y caja.
- Carga de tickers en bloque (bulk paste) en vez de uno por uno.
- Covarianza con shrinkage hacia la diagonal, comparada lado a lado
  con la covarianza muestral cruda.
- Beta/CAPM/Hamada validado contra caso de control, con comparación
  beta desapalancada vs. reapalancada.
- Valoración FCFF/WACC/valor terminal (inicialmente atada al caso
  "Alimentos del Norte", luego removida y generalizada en 0.2.1).
- Momentum como apoyo para formular una vista de Black-Litterman.
- Trazabilidad/exportación JSON del análisis de portafolio.
- Preset de 50 tickers reales de Yahoo Finance.

### Corregido
- Exigir observaciones comunes proporcionales a N activos (no un
  umbral fijo) para evitar Σ casi singular.
- Covarianza muestral sobreajustada producía Sharpe irreales (~3.8)
  con datos reales — resuelto con shrinkage.

## [0.1.0] — 2026-09-18 a 2026-09-24 — Núcleo v1 (RF-01 a RF-22)

### Agregado
- Identidad, disclaimer y política de ejecución (RF-01).
- Acceso OIDC Google/Microsoft, sesión lógica, auditoría,
  notificaciones (RF-02).
- Colección de tickers, fechas, frecuencia, horizonte (RF-03/RF-04).
- Descarga, limpieza y remuestreo de precios (RF-05 a RF-08).
- Análisis histórico: rendimientos logarítmicos, estadística
  descriptiva, drawdown (RF-09 a RF-12).
- Forecasting homocedástico con validación walk-forward (RF-13 a
  RF-15).
- VaR paramétrico, niveles de entrada/SL/TP, probabilidades terminales
  (RF-16 a RF-18).
- Comparación de activos, dominancia, exportación (RF-19 a RF-22).
- Ciclo de vida: revocación, purga programada, worker periódico
  (RNF-03).

### Corregido
- `ImportError` por un import muerto en `app.py` que rompía el
  despliegue en Streamlit Cloud.
- Conflicto de merge tras confirmar el consentimiento después del
  login.
