# Guía de uso — Robot Analítico TBS-EIA

Esta guía tiene dos partes: **instalación** (una sola vez) y **uso**
(cada vez que quieras trabajar con el bot).

---

## Parte 1 — Instalación (una sola vez)

### 1.1. Requisitos previos

- **Python 3.10 o superior** instalado en tu computador.
  Verificar: abre una terminal y escribe `python --version` (o
  `python3 --version` en Mac/Linux). Si no lo tienes, descárgalo de
  [python.org](https://www.python.org/downloads/).
- El archivo `tbs-eia-robot.zip` que te compartí.

### 1.2. Descomprimir el proyecto

1. Guarda `tbs-eia-robot.zip` en la carpeta donde quieras trabajar
   (ej. `Documentos/Universidad/`).
2. Descomprímelo (clic derecho → "Extraer aquí", o doble clic en Mac).
3. Vas a obtener una carpeta `tbs-eia-robot/` con archivos como
   `app.py`, la carpeta `src/`, etc.

### 1.3. Instalar las dependencias

1. Abre una terminal **dentro de esa carpeta**:
   - Windows: clic derecho en la carpeta → "Abrir en Terminal".
   - Mac: clic derecho → "Nueva Terminal en la carpeta" (o abre
     Terminal y escribe `cd ` seguido de arrastrar la carpeta).
2. Ejecuta:
   ```bash
   pip install -r requirements.txt
   ```
   Esto instala Streamlit, pandas, numpy, scipy y todo lo necesario.
   Tarda uno o dos minutos.

### 1.4. Configurar el acceso con Google y/o Microsoft

El bot exige iniciar sesión antes de dejarte usar las funciones
analíticas (RF-02 de la guía). Necesitas credenciales OAuth propias:

1. Copia el archivo de ejemplo:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
2. Sigue las instrucciones para crear credenciales de **Google**
   (Google Cloud Console → Pantalla de consentimiento OAuth →
   Credenciales → ID de cliente OAuth, tipo "Aplicación web", con URI
   de redirección `http://localhost:8501/oauth2callback`) y/o
   **Microsoft** (portal.azure.com → Microsoft Entra ID → Registros de
   aplicaciones), y pega el `client_id`/`client_secret` de cada una en
   `.streamlit/secrets.toml`.
3. Genera un `cookie_secret` aleatorio:
   ```bash
   openssl rand -hex 32
   ```
   y pégalo en el campo `cookie_secret` de `.streamlit/secrets.toml`.
4. Abre `src/auth.py` y agrega tu correo (el mismo con el que vas a
   iniciar sesión) a `ALLOWLISTED_TEST_EMAILS`. Sin este paso, el
   login funcionará pero la app te va a rechazar como "cuenta no
   autorizada" — es una medida de seguridad intencional del piloto.

**¿No quieres configurar OAuth todavía?** Puedes saltarte este paso e
igual explorar el código y correr las pruebas automatizadas (sección
1.5). Solo no vas a poder entrar a la app en el navegador sin login.

### 1.5. (Opcional) Verificar que todo funciona

```bash
pytest tests/ -v
```
Deberías ver `219 passed`. Esto no requiere configurar OAuth ni
internet — usa datos de prueba (fixtures) incluidos en el proyecto.

---

## Parte 2 — Uso del bot

### 2.1. Arrancar la aplicación

Desde la terminal, dentro de la carpeta del proyecto:
```bash
streamlit run app.py
```
Se abre automáticamente tu navegador en `http://localhost:8501`. Para
detenerla, vuelve a la terminal y presiona `Ctrl+C`.

### 2.2. Aceptar el disclaimer y el aviso de privacidad

Al entrar verás la identidad del sistema, la política de ejecución, el
**disclaimer académico** y el **aviso de privacidad** — son dos
checkboxes separados. Debes marcar ambos antes de que se habiliten los
botones de "Continuar con Google" / "Continuar con Microsoft".

### 2.3. Iniciar sesión

Haz clic en el botón del proveedor que configuraste (Google o
Microsoft). Te va a redirigir a un login real de ese proveedor. Una
vez autenticado, vuelves a la app ya con sesión activa (dura 30
minutos de inactividad u 8 horas en total, lo que ocurra primero).

### 2.4. Selección de activos (tickers)

En "Selección de activos": escribe un ticker (ej. `AAPL`, `MSFT`,
`BRK.B`) en el cuadro de texto y presiona "Agregar". Puedes eliminar
cualquiera con el botón ✕ junto a su nombre.

- **1 solo ticker** → modo análisis individual.
- **20 o más tickers** → se habilita el modo comparación.

### 2.5. Fechas, frecuencia y horizonte

Justo debajo, define:
- **Fecha inicial / fecha final** del histórico a analizar.
- **Frecuencia**: diaria, semanal o mensual.
- **Horizonte H**: escribe cualquier número de periodos hacia
  adelante, o cambia a "Fecha objetivo" y elige una fecha futura — el
  sistema la convierte a periodos automáticamente.

### 2.6. Descargar y limpiar datos

En "Descarga y calidad de datos", presiona **"Descargar y limpiar
datos"**. Por defecto usa el **fixture sintético del curso** (no
requiere internet ni es un dato de mercado real — ideal para probar
sin depender de un proveedor externo). Vas a ver una tabla con cada
ticker válido (observaciones, último precio, moneda, fuente) y, si
algún ticker falla, se lista aparte sin detener a los demás.

> Para usar datos reales de mercado en vez del fixture, hay que activar
> `YFinanceProvider` en `src/data.py` (ver nota en ese archivo) — no
> viene activado por defecto porque no se probó contra la red real en
> el entorno donde se construyó.

### 2.7. Análisis histórico de un activo

En "Análisis histórico", elige un ticker del menú desplegable (de los
que sí se descargaron bien). Vas a ver:
- Gráfico de precio y de rendimiento logarítmico en el tiempo.
- Último precio, último rendimiento, drawdown actual y máxima caída
  histórica.
- Tabla completa de estadísticas descriptivas (media, volatilidad
  anualizada, asimetría, curtosis, cuantiles).

### 2.8. Forecasting

En "Forecasting homocedástico", elige uno o ambos modelos (A =
caminata aleatoria, B = lognormal con deriva). Vas a ver la
trayectoria proyectada de 1 hasta H periodos, con banda de incertidumbre
(percentiles 5% y 95%), y — en un desplegable — los resultados de la
validación walk-forward (qué tan bien habría predicho el modelo en el
pasado reciente).

### 2.9. Riesgo y niveles de decisión

En "Riesgo, niveles de decisión y probabilidades", ajusta si quieres
la confianza del VaR (95% o 99%), el capital hipotético, los límites
de stop-loss/take-profit (p_L, p_U), y costos de compra/venta. El
sistema te muestra el VaR, los niveles de entrada/salida, y si hay
**"señal"** o **"no señal"** — con la razón exacta si no la hay.

### 2.10. Comparación y exportación

Si tienes 20 o más tickers descargados, aparece el **mapa histórico**
(volatilidad vs. media anualizada, cada punto etiquetado). Puedes
elegir una de 4 reglas de preselección y ver qué activo(s) cumplen.
Al final, tres botones de descarga: precios procesados, tabla
comparativa, y todo junto en un archivo JSON.

---

## Resumen rápido (por si ya lo instalaste antes)

```bash
cd tbs-eia-robot
streamlit run app.py
```
Y sigue el flujo: aceptar disclaimer/privacidad → login → agregar
tickers → configurar fechas/frecuencia/horizonte → descargar datos →
explorar análisis/forecasting/riesgo/comparación.
