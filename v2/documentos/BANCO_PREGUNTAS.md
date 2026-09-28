# Banco progresivo de 160 preguntas

Maestría en Finanzas. Universidad de Antioquia. BOT de Portafolios v2.

Se utiliza durante los incrementos con hasta seis preguntas por intercambio, no como un cuestionario previo. Las preguntas 129 a 152 profundizan rutas opcionales. Cada respuesta debe aportar decisión, mecanismo, supuesto, evidencia y contraste.

Las respuestas sustantivas se registran una vez en BITACORA. La IA no declara aprobada una defensa ni atribuye sus propias respuestas al estudiante.

## 1. Propósito, mandato y especialización

Evidencia: Mandato financiero de una página.

**P1.** ¿Qué decisión concreta debe mejorar el BOT, quién la tomará y qué evidencia demostrará esa mejora?

**P2.** ¿Qué ruta de escalamiento prioriza el equipo y por qué resuelve una necesidad más importante que agregar indicadores?

**P3.** ¿Qué restricciones provienen del inversionista, del instrumento y de una simplificación pedagógica, y cómo se distinguen?

**P4.** ¿Cómo traduce moneda, obligaciones, horizonte, liquidez y pérdida tolerable en límites verificables?

**P5.** ¿Qué significa óptimo para este inversionista y qué preferencia haría que otro eligiera una cartera distinta?

**P6.** ¿Qué decisiones financieras conservará cada estudiante y qué tareas puede delegar a la IA sin perder responsabilidad?

**P7.** ¿Qué resultado justificaría no invertir o no rebalancear aunque el optimizador entregue pesos?

**P8.** ¿Qué demostración pequeña podría refutar la idea inicial antes de construir todas las pantallas?

## 2. Datos de mercado y comparabilidad

Evidencia: Diccionario, muestra común y consultas identificadas.

**P9.** ¿Qué significa cada campo del proveedor y cómo verificará ajuste, dividendos, splits, bolsa y moneda?

**P10.** ¿Cómo distingue hora del negocio, de la barra, recepción y cálculo, y cuándo considera obsoleto un dato?

**P11.** ¿Qué calendario evita tratar feriados, suspensiones o precios estancados como nuevas observaciones?

**P12.** ¿Cómo evita convertir un hueco de varios días en un rendimiento diario después de eliminar fechas?

**P13.** ¿Qué ocurre si un activo tiene menos historia y cómo conserva visible el universo efectivamente optimizado?

**P14.** ¿Cómo convierte el rendimiento USD a COP y controla la asincronía del tipo de cambio?

**P15.** ¿Qué derechos permiten consultar, almacenar y mostrar los datos, y cuáles no concede yfinance?

**P16.** ¿Qué evidencia demuestra que el gráfico cambió por información nueva y no por una animación, un fixture o un reloj local?

## 3. Python y pandas

Evidencia: Transformaciones reproducibles y orden verificado.

**P17.** ¿Qué esquema tiene el DataFrame maestro y qué clave diferencia bolsa, clase de acción y revisión de un ticker?

**P18.** ¿Qué operaciones de pandas ordenan, deduplican, alinean y remuestrean, y qué decisión financiera implica cada una?

**P19.** ¿Por qué pct_change entrega una fracción y qué error aparece al confundir 0,01 con 0,01 %?

**P20.** ¿Cómo conserva el orden de activos entre DataFrame, arrays, pesos, Sigma y P?

**P21.** ¿Cuándo usa inner join, outer join y merge_asof hacia atrás para precios y anuncios?

**P22.** ¿Cómo maneja NaN, infinito, precios no positivos y fechas incompatibles sin esconderlos con ceros?

**P23.** ¿Cómo separa funciones numéricas puras, red e interfaz para probar sin conexión?

**P24.** ¿Qué elementos hacen reproducible un cálculo y cuáles pueden cambiar aunque la fecha histórica solicitada sea la misma?

## 4. Rendimientos y estimación

Evidencia: Control de agregación y convención temporal.

**P25.** ¿Por qué los logs se suman en el tiempo, pero una cartera se agrega con retornos simples y pesos iniciales?

**P26.** ¿Qué producen +10 % y -10 % con pesos iguales y qué sesgo introduce promediar sus logs?

**P27.** ¿Qué pregunta responde cada medida: media aritmética, geométrica, logarítmica y CAGR?

**P28.** ¿Qué supuesto permite multiplicar una covarianza por m y qué cambia con autocorrelación?

**P29.** ¿Cómo convierte rf efectiva anual y evita mezclarla con una media anualizada linealmente?

**P30.** ¿Cómo decide la ventana sin escoger retrospectivamente la que mejora la inversión?

**P31.** ¿Qué incertidumbre de la media podría invertir el ranking de dos activos y cómo la cuantifica?

**P32.** ¿Cómo diferencia rendimiento histórico, expectativa, retorno implícito y rendimiento requerido en cada vista?

## 5. Covarianza, correlación y estabilidad

Evidencia: Matrices manuales, PSD y estimadores contrastados.

**P33.** ¿Cómo reconstruye una covarianza centrando los datos y por qué ese estimador utiliza T-1?

**P34.** ¿Qué unidad tiene Sigma y qué pasa si introduce porcentajes en lugar de decimales?

**P35.** ¿Por qué correlación cero no demuestra independencia ni ausencia de dependencia en colas?

**P36.** ¿Cómo puede la eliminación por pares producir una matriz no PSD y qué resuelve una muestra común?

**P37.** ¿Cómo distingue singularidad, mal condicionamiento e indefinición, y cuál rompe la convexidad de la varianza?

**P38.** ¿Qué cambia cuando N se aproxima a T y por qué más tickers pueden deteriorar la estimación?

**P39.** ¿Qué problema busca corregir shrinkage o EWMA y cómo elige sus parámetros sin mirar la prueba?

**P40.** ¿Cómo separa el efecto de volatilidades y correlaciones sobre la pérdida de diversificación?

## 6. Riesgo individual y conjunto en línea

Evidencia: Pesos definidos, ventanas móviles y contribuciones.

**P41.** ¿Por qué el promedio ponderado de volatilidades no representa el riesgo del portafolio?

**P42.** ¿Qué falta para calcular el riesgo económico de una lista de activos sin pesos?

**P43.** ¿Cómo diferencia volatilidad por barra, variación realizada y volatilidad condicional estimada?

**P44.** ¿Cuántas barras completas necesita y qué desfase entre activos invalida el cálculo intradía?

**P45.** ¿Cómo calcula contribuciones al riesgo y cuándo una contribución negativa es una cobertura válida?

**P46.** ¿Qué limitaciones del VaR justifican añadir drawdown, pérdida en cola, liquidez y concentración?

**P47.** ¿Qué shock conjunto podría destruir la diversificación observada en la muestra?

**P48.** ¿Cómo atribuye un aumento de riesgo a deriva de pesos, cambio de Sigma o cambio de metodología?

## 7. Conjunto factible y fronteras

Evidencia: Restricciones y frontera obtenida por optimización.

**P49.** ¿Qué ecuaciones definen W y cómo comprueba que al menos una cartera satisface todas las restricciones?

**P50.** ¿Por qué miles de carteras simuladas no prueban haber encontrado la frontera eficiente?

**P51.** ¿Cómo obtiene las ramas eficiente y no eficiente al minimizar varianza para cada retorno objetivo?

**P52.** ¿Cómo distingue un activo no dominado, una cartera eficiente y un punto interior dominado?

**P53.** ¿Qué espera con dos activos de correlación -1, 0 y 1 y qué condiciones adicionales importan?

**P54.** ¿Cuándo es válida la GMV por fórmula inversa y cuándo exige un solver restringido?

**P55.** ¿Cómo cambian el máximo rendimiento y su acotación al permitir cortos o deuda?

**P56.** ¿Qué residuales y verificaciones exige además del mensaje success del optimizador?

## 8. Preferencias, tangencia, CAL, CML y SML

Evidencia: Objetivo personal y mercado diferenciados.

**P57.** ¿Cómo justifica gamma sin inferir preferencias personales de la historia de precios?

**P58.** ¿Por qué GMV o máxima razón Sharpe pueden no coincidir con el óptimo del inversionista?

**P59.** ¿Qué expresa la CAL y qué implica y mayor que uno sobre financiación y riesgo?

**P60.** ¿Cómo cambia la oportunidad si endeudarse cuesta más que invertir a rf?

**P61.** ¿Qué condiciones permiten denominar CML a una CAL y qué limita el proxy de mercado?

**P62.** ¿Por qué CML usa volatilidad y SML beta, y qué objetos pertenecen a cada relación?

**P63.** ¿Qué decisión adopta con premios esperados negativos y por qué normalizar un vector no basta para hallar tangencia?

**P64.** ¿Qué requiere matemáticamente la cuenta media-varianza y qué supuestos pertenecen a preferencias o equilibrio en vez de al cálculo?

## 9. Black-Litterman y prior

Evidencia: Prior y unidades de referencia documentados.

**P65.** ¿Qué debilidad de las medias históricas atiende BL y qué problema no resuelve?

**P66.** ¿De dónde salen los pesos del prior y cuándo pueden llamarse de mercado?

**P67.** ¿Por qué pi=delta*Sigma*w_ref está en exceso y cómo evita sumar rf dos veces?

**P68.** ¿Cómo estima o justifica delta y por qué no es gamma del inversionista?

**P69.** ¿Qué representan Sigma, tau*Sigma y Omega y por qué no son intercambiables?

**P70.** ¿Cómo representa una view absoluta y una relativa en P y Q manteniendo el orden de activos?

**P71.** ¿Por qué el patrimonio de un ETF no equivale a capitalización de su mercado subyacente?

**P72.** ¿Qué debe ocurrir sin views y cuando Q=P*pi, y bajo qué condiciones se recuperarían también los pesos iniciales?

## 10. Black-Litterman y opiniones

Evidencia: Views con evidencia, incertidumbre y refutación.

**P73.** ¿Qué tesis respalda cada view y qué observación podría contradecirla?

**P74.** ¿Cómo conecta crecimiento de ventas con retorno esperado sin tratarlos como la misma variable?

**P75.** ¿Cómo justifica incertidumbre de una view y por qué confianza no es probabilidad garantizada de ganancia?

**P76.** ¿Cómo maneja confianza cero, certeza y opiniones incompatibles?

**P77.** ¿Cómo impide duplicar la misma noticia mediante varias views o actualizaciones repetidas del posterior?

**P78.** ¿Cuándo vence una opinión y qué información reduce su confianza antes de esa fecha?

**P79.** ¿Por qué tau puede cancelarse en la media si Omega escala con él y qué incertidumbre podría seguir cambiando?

**P80.** ¿Cómo explica cambios en pesos BL con GMV invariable cuando Sigma y W permanecen fijas?

## 11. Rebalanceo y nueva información

Evidencia: Política por calendario y eventos.

**P81.** ¿Qué información activa rebalanceo y qué cambios solo actualizan precio o riesgo visual?

**P82.** ¿Cómo distingue actualización de cotizaciones, recalibración estadística y decisión de operar?

**P83.** ¿Cómo reconstruye los pesos que derivaron antes de compararlos con los nuevos objetivos?

**P84.** ¿Qué justifica el umbral de desviación, banda de no operación y espera mínima?

**P85.** ¿Qué hace si la cartera anterior deja de ser eficiente bajo el nuevo modelo, pero el cambio no cubre sus costos?

**P86.** ¿Cómo actualiza prior, views y elegibilidad sin reescribir una decisión pasada?

**P87.** ¿Cómo evita rebalanceos por eventos duplicados, splits o precios obsoletos?

**P88.** ¿Qué guarda de las fronteras anterior y nueva para explicar por qué cambió la decisión?

## 12. Ejecución simulada y prueba temporal

Evidencia: Posiciones, caja y costos reconciliados.

**P89.** ¿Qué fechas usa para información, decisión y ejecución, y cómo prueba que no negocia antes de conocer el dato?

**P90.** ¿Cómo convierte pesos a cantidades con lotes, caja, liquidez y activos no negociables?

**P91.** ¿Qué diferencia hay entre turnover unilateral y nominal negociado, y sobre cuál cobra costos?

**P92.** ¿Cómo comprueba V_post=V_pre-costos y separa aportes, retiros, dividendos y P&L?

**P93.** ¿Qué supuestos adopta para spread, slippage e impacto y cuáles corresponden a datos observados?

**P94.** ¿Cómo compara mantener cantidades, 1/N, GMV, Markowitz y BL con costos y períodos equivalentes?

**P95.** ¿Qué bloques de entrenamiento, validación y prueba no reutilizará al ajustar reglas?

**P96.** ¿Qué condición suspende la estrategia cuando pierde estabilidad o falla fuera de muestra?

## 13. Beta y econometría

Evidencia: Benchmark previo y estimación con incertidumbre.

**P97.** ¿Qué benchmark remunera el riesgo que interesa y qué exposición omite?

**P98.** ¿Cómo obtiene beta por covarianza/varianza y lo contrasta con OLS con intercepto?

**P99.** ¿Qué cambia si calcula beta de excesos con rf variable frente a retornos brutos?

**P100.** ¿Cómo interpreta error estándar, intervalo, R² y residuales sin reducir el diagnóstico a un p-valor?

**P101.** ¿Cómo afectan ventana, frecuencia, iliquidez y negociación asincrónica la estabilidad del beta?

**P102.** ¿Cuándo beta de cartera es suma ponderada de betas individuales y qué pesos usa?

**P103.** ¿Por qué seis observaciones sirven para el control de clase pero no acreditan precisión suficiente para valorar?

**P104.** ¿Por qué cambiar una view no modifica beta histórico del activo frente a benchmark fijo, aunque cambie el beta de la cartera?

## 14. Apalancamiento y rendimiento requerido

Evidencia: Hamada y CAPM coherentes con el riesgo.

**P105.** ¿Qué parte del beta corresponde al negocio y cuál al apalancamiento del comparable?

**P106.** ¿Qué partidas entran en D/E y por qué no puede mezclar pasivos operativos, deuda financiera y libros sin explicarlo?

**P107.** ¿Qué supuesto permite beta_D=0 y qué fórmula cambia si la deuda es riesgosa?

**P108.** ¿Cómo trata circularidad cuando D/E usa el valor patrimonial que se está calculando?

**P109.** ¿Cómo selecciona rf y ERP por moneda y plazo sin confundir expectativa con retorno requerido?

**P110.** ¿Cómo incorpora riesgo país y exposición sin cobrarlo dos veces?

**P111.** ¿Qué supuesto sostiene la conversión por inflaciones y por qué no predice ciertamente la TRM?

**P112.** ¿Qué decide si más deuda eleva ROE, Ke, costo de deuda y riesgo de incumplimiento a la vez?

## 15. Empresa, presupuesto y valoración

Evidencia: Flujos, reinversión y tasa consistente.

**P113.** ¿Cómo usa Ke para una meta presupuestal sin igualar ROE contable con rentabilidad de mercado?

**P114.** ¿Qué ventas, márgenes y gastos cerrarían la brecha de EBIT y qué evidencia de negocio los respalda?

**P115.** ¿Cómo resuelve el bucle ventas-capacidad-CAPEX-depreciación con tolerancia comprobable?

**P116.** ¿Qué distingue utilidad, FCFF, FCFE y dividendo disponible y qué tasa aplica a cada flujo?

**P117.** ¿Cómo reconcilia EV y patrimonio sin duplicar caja, deuda u otros ajustes?

**P118.** ¿Qué reinversión y ROIC sostienen g terminal y cuándo CAPEX=depreciación es incompatible con crecer?

**P119.** ¿Cómo actualiza beta, Ke y WACC si cambia D/E en la valoración?

**P120.** ¿Qué supuesto domina el valor y qué combinación de margen, tasa o reinversión refuta la tesis?

## 16. Pensamiento sistémico y escucha

Evidencia: Exposiciones, escenarios y revisión de tesis.

**P121.** ¿Qué sectores, monedas, insumos y tasas conectan las posiciones entre sí y con la empresa?

**P122.** ¿Qué información representa sorpresa frente a expectativas y cuál era conocida por el mercado?

**P123.** ¿Qué mecanismos y rezagos conectan una subida de tasas con margen, caja y precio de acciones?

**P124.** ¿Qué retroalimentación entre pérdidas, liquidez y ventas forzadas puede amplificar el shock?

**P125.** ¿Cómo distingue régimen y ruido, considerando el costo de reaccionar pronto o tarde?

**P126.** ¿Qué evidencia adversa hizo cambiar una tesis y cómo modificó su magnitud o confianza?

**P127.** ¿Qué escenario inverso identifica la combinación que rompe riesgo, caja o covenants?

**P128.** ¿Qué decisión se sostiene con modelos rivales y cuál depende de un supuesto frágil?

## 17. Ruta de análisis técnico

Evidencia: Hipótesis falsable, señal y ejecución temporal.

**P129.** ¿Qué mecanismo financiero respalda el indicador y por qué añade valor frente a observar el precio?

**P130.** ¿Qué ajuste, precio, volumen y frecuencia requiere y cómo maneja barras incompletas?

**P131.** ¿Cuándo se conoce la señal y qué precio posterior podría ejecutarse?

**P132.** ¿Cómo distingue momentum, reversión y ruptura sin cambiar de definición después de perder?

**P133.** ¿Qué benchmark y costos podrían explicar toda su ventaja aparente?

**P134.** ¿Cómo limita búsqueda de parámetros y pruebas múltiples para no seleccionar ruido?

**P135.** ¿Cómo convierte la señal en view BL sin duplicar la evidencia que ya usa el modelo?

**P136.** ¿Qué resultado fuera de muestra obligaría a retirar el indicador aunque el backtest completo sea atractivo?

## 18. Ruta fundamental y proyectos

Evidencia: Fuentes publicadas y flujos incrementales.

**P137.** ¿Qué estados financieros estaban publicados a la fecha y cómo conserva reexpresiones?

**P138.** ¿Cómo normaliza no recurrentes, arrendamientos y partidas financieras sin manipular múltiplos?

**P139.** ¿Qué relación une ROIC, reinversión, ventaja competitiva, crecimiento y valor?

**P140.** ¿Cómo elige comparables por negocio y riesgo en vez del múltiplo que desea obtener?

**P141.** ¿Qué flujo es incremental, costo hundido, costo de oportunidad o canibalización en un proyecto?

**P142.** ¿Qué tasa corresponde al proyecto y qué error aparece al usar siempre el WACC corporativo?

**P143.** ¿Cómo trata exclusión mutua, distinta vida y conflicto entre VPN y TIR?

**P144.** ¿Qué evidencia justificaría posponer o abandonar, y cómo evita contar esa flexibilidad dos veces?

## 19. Ruta macro y trading cuantitativo

Evidencia: Vintages, señales y robustez fuera de muestra.

**P145.** ¿Qué mecanismo respalda la variable macro elegida y cómo evita una correlación hallada por búsqueda?

**P146.** ¿Cómo conserva publicación, revisión y expectativa para no usar información futura?

**P147.** ¿Qué trigger define activación, salida, persistencia, enfriamiento y vencimiento?

**P148.** ¿Cómo diferencia predicción estadística, causalidad y prima de un modelo multifactorial?

**P149.** ¿Qué presupuesto de riesgo y límites fija antes de evaluar ganancias?

**P150.** ¿Cómo evalúa estacionariedad, cointegración, costos y capacidad en una estrategia de pares?

**P151.** ¿Qué controles impiden convertir una búsqueda masiva en un Sharpe producto del azar?

**P152.** ¿Qué dato suspende la simulación y qué mandato distinto sería necesario antes de operar dinero real?

## 20. Trazabilidad, defensa y experiencia

Evidencia: Reproducción y dominio individual.

**P153.** ¿Cómo sigue un dato desde fuente/campo hasta muestra, fórmula, solver, peso y decisión?

**P154.** ¿Qué archivos y hashes reproducen la decisión sin reemplazarla por una versión de datos posterior?

**P155.** ¿Qué explicó, decidió, corrigió y probó cada integrante frente a lo que produjo la IA?

**P156.** ¿Qué cálculo y cambio breve puede realizar cada estudiante sin IA para demostrar dominio?

**P157.** ¿Cómo comunica retraso, incertidumbre y ausencia de señal sin insinuar una recomendación real?

**P158.** ¿Cómo mantiene contexto, foco, unidades y tabla accesible cuando se actualizan gráficos?

**P159.** ¿Qué pruebas negativas intentan romper el sistema y qué evidencia demuestra el fallo antes de corregirlo?

**P160.** ¿Qué diferencia existe entre validar este paquete, validar el BOT, publicar y aceptar la defensa, y qué falta en cada nivel?
