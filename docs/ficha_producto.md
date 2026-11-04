# Ficha del producto — Botiverso

*Material para la Guía de Sustentación Final (sección 1 "Ficha del producto").
Base para la diapositiva 2 ("Producto y oferta de valor") y la diapositiva 1
("Usuario y problema") de la secuencia de 10 minutos.*

## Producto final

- **Nombre:** Botiverso.
- **Propósito:** preseleccionar activos individualmente (rendimiento, riesgo,
  pronóstico, VaR) y, sobre ese universo ya filtrado, construir y evaluar
  portafolios de inversión (Markowitz, Black-Litterman, CAPM, valoración)
  con su validación cuantitativa.
- **Funciones entregadas:**
  - Análisis de un activo o comparación simultánea de 20+ activos con datos
    reales de Yahoo Finance (rendimiento, riesgo, pronóstico, VaR, niveles
    de entrada/SL/TP, probabilidades).
  - Matriz de correlación en vivo.
  - Portafolios óptimos (GMV, tangente, óptimo personal, máximo retorno) con
    frontera eficiente y Línea del Mercado de Capitales (CML).
  - Black-Litterman (prior, views, posterior) y rebalanceo simulado con
    costos.
  - Beta/CAPM/Hamada con Línea del Mercado de Títulos (SML) para todos los
    activos, descomposición de riesgo sistemático/no sistemático (R²), y
    beta sectorial externo opcional (ej. Damodaran).
  - Desempeño vs. benchmark: Sharpe, Treynor, alfa de Jensen, Information
    Ratio.
  - Valoración CAPM → patrimonio (FCFF/WACC/valor terminal), generalizada a
    cualquier caso.
  - Ficha técnica de portafolio estilo FIC (Decreto 1242/2013) para las
    carteras tangente, mínimo riesgo y mayor rendimiento.
  - Exportación/trazabilidad en JSON de cada análisis.
- **Entradas:** tickers (manual o preset curado), rango de fechas,
  frecuencia (diaria/semanal/mensual), horizonte, parámetros de riesgo (rf,
  gamma, nivel de confianza de VaR, costos de rebalanceo, beta sectorial
  manual).
- **Salidas:** tablas y gráficos interactivos, métricas numéricas, archivos
  JSON/CSV descargables con fecha, fuente y parámetros declarados.
- **Límites conocidos:** solo posiciones largas, sin apalancamiento real,
  sin ejecución de órdenes (la demostración en vivo usa datos reales de
  mercado pero no opera); universo limitado a lo que cubre Yahoo Finance;
  la ficha técnica estilo FIC es una aproximación de buena fe, no
  verificada contra el Anexo 6 exacto de la Circular Básica Jurídica
  (no se pudo acceder a ese documento en este entorno de desarrollo).

## Usuario

- **Perfil:** estudiante de finanzas o analista individual.
- **Necesidad:** filtrar rápido un universo grande de activos candidatos
  antes de comprometerse a construir un portafolio, y luego decidir una
  asignación de capital defendible con una tesis que pueda explicar.
- **Situación de uso:** antes de tomar (o simular) una decisión de
  inversión, o como ejercicio académico de aplicación de Teoría Moderna
  de Portafolios — quién se beneficia es el mismo usuario que opera el
  bot, no un tercero.

## Problema

- **Dificultad concreta:** revisar manualmente rendimiento, riesgo y
  pronóstico de 20 o más activos, uno por uno, es lento y propenso a
  errores; hacerlo además de forma consistente con la construcción de un
  portafolio óptimo y su validación (CAPM, VaR, ficha técnica) a mano es
  todavía más costoso y fácil de hacer mal.
- **Cómo se resuelve hoy:** hojas de cálculo construidas a mano activo por
  activo, o herramientas/terminales pagas (tipo Bloomberg) fuera del
  alcance de un estudiante.
- **Evidencia del equipo:** dos casos reales encontrados probando la app
  con datos de Yahoo Finance, no hipotéticos — (1) Markowitz "crudo"
  producía Sharpe irrealmente altos (~3.8) por sobreajuste de la
  covarianza muestral con pocas observaciones relativas a N activos
  (resuelto con shrinkage comparado lado a lado); (2) una regla de
  preselección que inicialmente parecía sospechosa por elegir siempre el
  mismo activo resultó, al verificar a mano, ser una dominancia real
  (JNJ), no un error — evidencia de que el bot necesitaba declarar sus
  supuestos para poder distinguir ambos casos.

## Oferta de valor

- Analiza un activo o compara veinte o más simultáneamente, con datos
  reales de Yahoo Finance.
- Calcula rendimiento, riesgo, pronóstico y niveles de decisión — todo
  verificado matemáticamente contra los casos oficiales del curso.
- Nunca promete más de lo que puede sostener: cuando los datos no
  alcanzan o el modelo no tiene sentido, dice explícitamente "no hay
  señal" en vez de inventar una recomendación.
- Acceso seguro real con Google — no es una maqueta, es un sistema con
  login, sesión y auditoría funcionando de verdad.
- **Diferencia frente a la alternativa actual** (hoja de cálculo manual o
  herramientas sin declarar supuestos): Botiverso declara explícitamente
  sus propios límites matemáticos (observaciones insuficientes, varianza
  indefinida, beta sin sentido con benchmark constante) como parte del
  producto, no como una nota al pie — y cubre en una sola interfaz lo que
  de otra forma exige saltar entre varias hojas y fórmulas sueltas.

## Resultados

- **Técnica:** 339/339 pruebas automatizadas pasando; cada fórmula
  financiera verificada contra un caso de control oficial del curso o
  derivado a mano (ver `TRACEABILITY.md`).
- **De uso:** demostración en vivo posible con datos reales de mercado,
  interfaz desplegada con login real (Google/Microsoft OIDC) y sesión
  auditada — no es una maqueta.
- **Todavía esperada:** validación de `YFinanceProvider` contra la red
  real en un entorno de producción sostenido (solo probado en local hasta
  ahora); retroalimentación del docente en la sustentación del 9 de
  noviembre.

## Dirección futura

- **Aplicación objetivo:** construcción y seguimiento de portafolios de
  inversión para un analista o estudiante individual.
- **Mejora prioritaria:** despliegue público estable en Streamlit Cloud
  con URL HTTPS verificada, y conversión FX explícita COP/USD (hoy los
  activos en distinta moneda se bloquean en vez de convertirse).
- **Evidencia para decidir continuar:** retroalimentación de la
  sustentación final y si el equipo sigue usando o mostrando la
  herramienta después de cerrado el curso.

Ver también `README.md` (secciones "Personalidad y diferenciación" y
"Plan de crecimiento") y `AI_USAGE.md` para el detalle sesión por sesión
de cómo se construyó cada pieza.
