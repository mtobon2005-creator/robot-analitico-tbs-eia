# Matriz de evolución — Botiverso

*Material para la Guía de Sustentación Final (sección 2 "Matriz de
evolución"). Base para la diapositiva 3 ("Base asignada y avances", 2 min)
de la secuencia de la sustentación. Fuente: historial real de commits y
`AI_USAGE.md` — nada aquí está inventado para la presentación, cada fila
tiene un commit o archivo verificable.*

## Requisito o función

| Primera versión | Versión final | Evidencia y utilidad |
|---|---|---|
| La base asignada (`Guia_Evaluativa_Bot.pdf`) analiza el riesgo total de cada activo por separado. Alcance explícito: "No calcula covarianzas, pesos, frontera eficiente ni un portafolio". | Markowitz N activos completo: mínima varianza, tangente, óptimo personal, máximo retorno, frontera eficiente y Línea del Mercado de Capitales (CML). | `src/portfolio.py`, `test_v2_portfolio.py` (22 casos, control analítico de 2 activos derivado a mano + universo sintético de 20). Beneficio: el usuario ya no se queda en "¿qué tan riesgoso es este activo?" sino que llega a "¿cuánto capital le asigno?". |
| Covarianza muestral pura (sin shrinkage) para optimizar. | Covarianza con shrinkage hacia la diagonal, mostrada lado a lado con la versión cruda. | `src/covariance.py::shrink_to_diagonal`, comparación en la UI de Portafolio v2. Beneficio: Sharpe realista en vez de inflado por sobreajuste (ver fila de "Observación recibida" correspondiente). |
| Beta calculado manualmente entre dos activos elegidos por el usuario, uno a la vez. | Línea del Mercado de Títulos (SML): beta, R² y rendimiento requerido CAPM para **todos** los activos descargados en una sola tabla y gráfico, con descomposición de riesgo sistemático/no sistemático. | `src/performance.py::systematic_risk_share`, `app.py::_render_sml_desempeno_v2`. Beneficio: ya no hay que repetir el cálculo activo por activo para ver el panorama completo del universo. |
| Sin métricas de desempeño ajustado por riesgo más allá del Sharpe de cada cartera. | Treynor, alfa de Jensen e Information Ratio de la cartera elegida contra un benchmark definido. | `src/performance.py`, 14 pruebas con valores derivados a mano o cruzados por script. Beneficio: distingue premio por riesgo sistemático (Treynor) de total (Sharpe), y mide si la cartera le ganó a su benchmark de forma consistente (Information Ratio), no solo en promedio. |
| Valoración FCFF/WACC/valor terminal hardcodeada al caso de control "Alimentos del Norte" de la guía. | Formulario de valoración genérico — cualquier empresa, con beta sectorial externo opcional (ej. Damodaran) en vez del comparable calculado. | Commit `45f12d3` "Generaliza la valoración CAPM->patrimonio". Beneficio: el usuario valora su propio caso, no uno fijo del curso. |
| Sin ficha técnica de portafolio. | Ficha técnica estilo FIC (Decreto 1242/2013) para las tres carteras obligatorias (tangente, mínimo riesgo, mayor rendimiento), con objetivo, restricciones, pesos, indicador de riesgo y advertencia regulatoria. | `app.py::_render_ficha_tecnica`, commit `6322e98`. Beneficio: consolida en un solo documento descargable lo que antes estaba disperso en varias secciones. |

## Observación recibida

| Problema señalado | Decisión tomada y estado | Comparación verificable y efecto |
|---|---|---|
| "NO ME FUNCIONA LO DE ELEGIR LOS ACTIVOS" (Mariana) — el selector de tickers no reflejaba cambios en producción. | Causa raíz: el fix solo se había mergeado a la rama de desarrollo, no a `main` (Streamlit Cloud despliega desde `main`). Decisión: fusionar siempre a `main` después de cada cambio verificado. Corregido. | Flujo de trabajo documentado en `README.md`, sección "Mandato v2". Desde entonces, cero reincidencias del síntoma. |
| "creo que no funciona bien con los datos de yahoo" + datos reales pegados mostrando Sharpe ~3.8 (Mariana). | Causa raíz: covarianza muestral sobreajustada al ruido con pocas observaciones relativas a N activos. Decisión: agregar shrinkage hacia la diagonal como comparación, y exigir un mínimo de observaciones proporcional a N (no un umbral fijo). Corregido. | `test_v2_covariance.py`; advertencia explícita en la UI cuando las observaciones son insuficientes, con el número exacto de años necesarios según la frecuencia elegida. |
| "quita lo del caso alimentos del norte, eso no debe de estar ahí, es más de guía" (Mariana). | Decisión: remover por completo la sección de valoración de la app en vivo (quedó solo como material de presentación aparte). Más tarde, cuando el correo del profesor pidió explícitamente valoración CAPM→patrimonio para la versión final, se reconstruyó generalizada (no atada a ningún caso). | Commits `bd52bc4` (remoción) y `45f12d3` (reconstrucción generalizada). |
| "haz que se vea porfa, solo está el título" (Mariana) — el logo de Botiverso no se veía en producción, solo el texto. | Causa raíz: el SVG incrustado crudo vía `st.markdown(unsafe_allow_html=True)` caía al tamaño por defecto del navegador dentro de un `<div>` sin ancho forzado. Decisión: cambiar a `st.image()`, que Streamlit maneja nativamente para SVG. Corregido y verificado visualmente con una captura headless (Playwright). | Commit `aa539f8`. Captura antes/después confirmó el ícono, el nombre y el tagline completos. |
| Correo del profesor sobre la versión final: faltaban correlación en vivo, beta vs. índice/portafolio óptimo, valoración generalizada con beta sectorial opcional, y ficha técnica consolidada. | Decisión: implementar los cuatro de inmediato, cada uno con pruebas y verificación antes de fusionar a `main`. Corregido. | Commits `071b1f6`, `45f12d3`, `382af31`. |

## Nueva aplicación

| Necesidad que la base asignada no atendía | Capacidad implementada para el usuario elegido | Resultado observable |
|---|---|---|
| Decidir cuánto capital asignar a cada activo según la aversión al riesgo propia del inversionista — la base v1 solo evaluaba activos uno por uno, nunca llegaba a una decisión de asignación. | Óptimo personal vía maximización de utilidad media-varianza `U(w)=w'mu-(gamma/2)*w'Sigma*w`, con gamma como parámetro explícito del usuario (no inferido de los precios). | Tabla "Carteras clave" en Portafolio v2, con pesos reales por activo para GMV, tangente, óptimo personal y máximo retorno. |
| Reaccionar a información nueva (una vista propia, un evento de mercado) ajustando la cartera ya construida — la base v1 no tenía ningún mecanismo de seguimiento en el tiempo. | Black-Litterman para incorporar una vista propia sobre un activo (con apoyo de momentum para formularla), y rebalanceo simulado con costos y caja hacia cualquiera de las carteras calculadas. | Tabla de operaciones (comprar/vender) con costos totales y turnover, sección "Rebalanceo simulado". |
| Comparar el desempeño de la cartera elegida contra una referencia externa, aislando qué parte del riesgo es diversificable — no existía ninguna métrica de ese tipo. | Treynor, alfa de Jensen e Information Ratio de la cartera vs. un benchmark elegido por el usuario, más la descomposición de riesgo sistemático/no sistemático (R²) de cada activo. | Sección "Desempeño de la cartera vs. benchmark", con métricas numéricas directamente comparables entre carteras. |
| Comunicar los resultados de un portafolio en un formato reconocible fuera del curso, no solo como tablas sueltas de la app. | Ficha técnica estilo FIC (Decreto 1242/2013, Art. 3.1.1.9.8) con la advertencia regulatoria verbatim del Art. 3.1.1.9.3, exportable a JSON. | Tres fichas descargables (tangente, mínimo riesgo, mayor rendimiento) en la sección "Ficha técnica del portafolio". |

Ver `AI_USAGE.md` para el detalle completo sesión por sesión (incluye
fecha real por commit) y `TRACEABILITY.md` para la matriz requisito →
implementación → prueba → rúbrica.
