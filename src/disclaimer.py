"""Disclaimer académico y política de ejecución (RF-01, sección 3.2 y 3.3).

El texto de DISCLAIMER_TEXT es el "texto mínimo obligatorio" literal de la
guía evaluativa. No debe reducirse su alcance; se permiten ajustes de
diseño (tipografía, layout) pero no de contenido.
"""

DISCLAIMER_VERSION = "1.0"

DISCLAIMER_TEXT = (
    "Esta aplicación fue desarrollada exclusivamente como actividad "
    "evaluativa del curso Teoría Moderna de Portafolios de Tech Business "
    "School - Universidad EIA. Sus datos, modelos y resultados tienen "
    "fines académicos y educativos. En ningún momento constituye "
    "asesoría financiera, recomendación de inversión ni una herramienta "
    "para tomar decisiones de inversión en la vida real. Es una "
    "herramienta académica que deberá revisarse, validarse y ajustarse, "
    "y puede contener errores, omisiones, rezagos o información "
    "incompleta. El sistema no ejecuta operaciones ni garantiza "
    "resultados."
)

# Política de ejecución (RF-01, 3.2): el "contrato lógico" del sistema.
# Debe ser reproducible con los mismos datos y parámetros, y visible
# antes de interpretar cualquier resultado.
EXECUTION_POLICY_VERSION = "1.0"

EXECUTION_POLICY_SECTIONS = {
    "Universo": (
        "Acciones individuales negociadas en mercados públicos. "
        "Tratamiento de monedas: se exige moneda base común entre los "
        "activos comparados; sin conversión declarada, activos en "
        "monedas incompatibles se bloquean de la comparación (RF-20)."
    ),
    "Datos": (
        "Precios ajustados por dividendos, splits y demás acciones "
        "corporativas, cuando la fuente los ofrezca. Se muestra "
        "proveedor, zona horaria y fecha del último dato disponible "
        "(RF-05)."
    ),
    "Acceso y privacidad": (
        "Acceso exclusivo mediante OIDC (Google o Microsoft). No existe "
        "acceso anónimo a las funciones analíticas. Datos mínimos: "
        "(issuer, subject), nombre y correo de la cuenta autenticada. "
        "Retención y eliminación según el ciclo de vida documentado en "
        "TRACEABILITY.md."
    ),
    "Posición": "Únicamente posición larga para el núcleo obligatorio.",
    "Ventana y frecuencia": (
        "Fechas inicial y final seleccionables por el usuario; "
        "periodicidad diaria, semanal o mensual; mínimo de "
        "observaciones exigido por el módulo de validación walk-forward."
    ),
    "Rendimiento": (
        "Exclusivamente logarítmico: g_t = ln(P_t / P_(t-1)). No existe "
        "ruta de cálculo basada en rendimientos simples."
    ),
    "Horizonte": (
        "Cantidad entera positiva de periodos definida por el usuario, "
        "en la frecuencia seleccionada, o una fecha objetivo que el "
        "sistema convierte de forma transparente."
    ),
    "Modelo": (
        "Modelo A (caminata aleatoria sin deriva, benchmark obligatorio) "
        "y Modelo B (lognormal con deriva y parámetros constantes), "
        "ambos homocedásticos. Selección de uno o varios para el mismo "
        "horizonte."
    ),
    "Riesgo": (
        "VaR paramétrico individual al 95% (obligatorio) y 99% "
        "(habilitable), con capital hipotético definido por el usuario."
    ),
    "Entrada y salidas": (
        "Entrada = último precio ajustado válido. Stop-loss y "
        "take-profit derivados de los cuantiles del modelo seleccionado "
        "en el horizonte H, con costos de compra/venta configurables."
    ),
    "Selección": (
        "Regla explícita elegida por el usuario: máxima media bajo "
        "límite de riesgo, mínima volatilidad bajo media mínima, máxima "
        "razón media-volatilidad, o conjunto no dominado. Nunca se "
        "presenta como frontera eficiente ni como mejor inversión "
        "universal."
    ),
    "No operar": (
        "El sistema emite 'no señal' cuando los datos son insuficientes, "
        "desactualizados o inválidos; cuando el diagnóstico homocedástico "
        "es débil sin advertencia declarada; cuando los niveles "
        "terminales son incoherentes (SL_H ≥ E, o E ≥ TP_H); o cuando el "
        "modelo falla numéricamente."
    ),
    "Limitaciones": (
        "Los resultados dependen enteramente de los datos históricos "
        "provistos, del supuesto de varianza constante (homocedasticidad) "
        "y no constituyen garantía de resultados futuros."
    ),
}
