# Robot Analítico TBS-EIA

Actividad evaluativa — Teoría Moderna de Portafolios, Tech Business
School / Universidad EIA. Ver `Guia_Evaluativa_Bot.pdf` para el alcance
completo (RF-01 a RF-22, RNF-01 a RNF-05).

## Estado actual (este commit)

**Núcleo obligatorio completo (RF-01 a RF-22) + lifecycle_worker**
(221/221 pruebas pasando):

- RF-01 a RF-22: ver secciones anteriores — todo verificado contra los
  casos oficiales de la matriz de pruebas.
- **Ciclo de vida (`src/lifecycle.py`, RNF-03)**: revocación inmediata
  (bloquea sesión y purga en cascada perfil/consentimientos/sesiones/
  eventos/outbox), purga programada al cierre del curso (`purge_at` =
  la menor entre una solicitud válida y 90 días tras la firmeza de la
  calificación), worker periódico que además vence flujos de
  preconsentimiento no consumidos (>15 min) y expira `deletion_markers`
  vencidos, y reaplicación de la purga tras restaurar un respaldo
  (T-23) — nunca guarda el identificador crudo del usuario, solo un
  HMAC. Ejecutable como proceso independiente: `python -m src.lifecycle`.

⚠️ **Limitaciones conocidas** (documentarlas en TRACEABILITY.md):

1. `src/consent.py` — la cookie HttpOnly literal del preconsentimiento
   no es 100% nativa en Streamlit puro.
2. `src/horizon.py` — la conversión "fecha objetivo → periodos" es una
   aproximación de calendario.
3. `src/data.py` — `YFinanceProvider` está implementado pero SIN
   probar contra la red real.
4. `src/lifecycle.py` — la purga de "logs técnicos sin PII a los 14
   días" y "respaldos con vencimiento máximo de 30 días" (sección 3.4)
   depende de infraestructura de hosting/backups que este piloto no
   controla directamente (la BD/sink los provee el curso, punto 46);
   el código asume que esa infraestructura respeta esos plazos por
   configuración externa, no los aplica él mismo.

**Aún falta para el 100% de la rúbrica:**
- Pruebas de integración/infraestructura restantes de la sección 8
  (T-19 a T-25: Google/Microsoft con cuentas reales — ya verificado
  manualmente en local; sesión con reruns/pestañas concurrentes,
  healthcheck, accesibilidad).
- Video de defensa de máx. 5 minutos.
- Reemplazar los placeholders de equipo (`src/config.py`,
  `CONTRIBUTIONS.md`) una vez esté conformado.
- Mejoras opcionales (sección 9.1) — ninguna necesaria para 100 puntos.

## Documentación de cierre

- **`TRACEABILITY.md`** — matriz completa RF/RNF → implementación →
  pruebas → rúbrica → estado, con las limitaciones conocidas resumidas.
- **`AI_USAGE.md`** — registro sesión por sesión del uso de IA
  generativa en la construcción del proyecto.
- **`CONTRIBUTIONS.md`** — plantilla de asignación de módulos por
  integrante (equipo aún sin conformar).

## Ejecutar localmente

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Editar .streamlit/secrets.toml con credenciales reales de Google/Microsoft
# (cuentas de prueba — ver punto 63 de la guía) y un cookie_secret generado con:
#   openssl rand -hex 32
streamlit run app.py
```

Para correr el worker de notificaciones manualmente (normalmente lo
haría un scheduler cada minuto):

```bash
python -m src.notifications_worker
```

Para correr el worker de ciclo de vida manualmente (normalmente lo
haría un scheduler al menos una vez al día — requiere la variable de
entorno `LIFECYCLE_HMAC_SECRET`):

```bash
export LIFECYCLE_HMAC_SECRET=$(openssl rand -hex 32)  # guardar en el gestor de secretos, no perder
python -m src.lifecycle
```

## Estructura

```
app.py                     # entrada, navegación, guard de acceso
src/config.py               # identidad del sistema (EDITAR con datos del equipo)
src/disclaimer.py            # texto obligatorio del disclaimer + política de ejecución
src/privacy.py                # aviso de privacidad
src/db.py                      # conexión SQLite + transacciones atómicas
src/consent.py                  # preconsentimiento de un solo uso
src/sessions.py                  # sesión lógica, TTL, guard
src/audit.py                      # auth_events (inmutable)
src/notifications.py               # creación de la intención de notificación
src/notifications_worker.py         # worker con reintentos e idempotencia
src/auth.py                          # orquestador: allowlist + login atómico
src/tickers.py                        # RF-03: colección dinámica de tickers
src/horizon.py                        # RF-04: fechas, frecuencia, horizonte H
src/data.py                            # RF-05 a RF-08: descarga, limpieza, remuestreo
src/analytics.py                       # RF-09 a RF-12: rendimientos, estadísticas, drawdown
src/forecasting.py                     # RF-13 a RF-15: forecasting homocedástico, walk-forward
src/risk.py                            # RF-16 a RF-18: VaR, niveles, probabilidades
src/comparison.py                      # RF-19 a RF-21: mapa comparativo, dominancia, selección
src/export.py                          # RF-22: exportación (precios, comparativa, y por activo)
src/lifecycle.py                       # RNF-03: revocación, purga programada, worker periódico
migrations/001_init.sql               # esquema de las 8 entidades mínimas
.streamlit/secrets.toml.example        # plantilla de credenciales OIDC (NO subir el real)
tests/unit/                             # pruebas unitarias
tests/integration/                       # pruebas de flujo completo (login atómico)
tests/fixtures/                           # fixtures oficiales del curso (verificados por SHA256SUMS.txt)
```

## Equipo

**Pendiente de conformar** (3-4 integrantes según la guía, punto 1
"Ficha de la actividad"). Editar `src/config.py` → `APP_IDENTITY` en
cuanto esté definido.

## Licencia

Ver [`LICENSE`](LICENSE) — MIT con nota de uso académico (alineada con
el disclaimer de `src/disclaimer.py`).

## Referencias (APA 7)

Las mismas fuentes que fundamentan la guía evaluativa, porque este
proyecto implementa exactamente esos modelos y esas convenciones —
ver `src/forecasting.py`, `src/risk.py`, `src/lifecycle.py`, `src/db.py`
y `src/consent.py` para dónde se aplica cada una.

CFA Institute. (2024a). *CFA Program curriculum 2025: Level I, volume
&nbsp;&nbsp;&nbsp;&nbsp;9: Portfolio management.*

CFA Institute. (2024b). *CFA Program curriculum 2025: Level III core,
&nbsp;&nbsp;&nbsp;&nbsp;volume 1: Asset allocation.*

Congreso de Colombia. (2012, 17 de octubre). *Ley 1581 de 2012, por la
&nbsp;&nbsp;&nbsp;&nbsp;cual se dictan disposiciones generales para la
protección de datos personales.*
https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=49981

Francis, J. C., & Kim, D. (2013). *Modern portfolio theory:
&nbsp;&nbsp;&nbsp;&nbsp;Foundations, analysis, and new developments.*
John Wiley & Sons.

Google. (2026, 15 de junio). *OpenID Connect.* Google for Developers.
https://developers.google.com/identity/openid-connect/openid-connect

Lodderstedt, T., Bradley, J., Labunets, A., & Fett, D. (2025). *Best
&nbsp;&nbsp;&nbsp;&nbsp;current practice for OAuth 2.0 security* (BCP
240, RFC 9700). RFC Editor. https://doi.org/10.17487/RFC9700

Microsoft. (2026, 30 de junio). *OpenID Connect (OIDC) on the
&nbsp;&nbsp;&nbsp;&nbsp;Microsoft identity platform.* Microsoft Learn.
https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc

OWASP Foundation. (2025). *OWASP application security verification
&nbsp;&nbsp;&nbsp;&nbsp;standard* (Version 5.0.0).
https://owasp.org/www-project-application-security-verification-standard/

Souppaya, M., Scarfone, K., & Dodson, D. (2022). *Secure Software
&nbsp;&nbsp;&nbsp;&nbsp;Development Framework (SSDF) version 1.1:
Recommendations for mitigating the risk of software vulnerabilities*
(NIST Special Publication 800-218). National Institute of Standards
and Technology. https://doi.org/10.6028/NIST.SP.800-218

Streamlit. (s. f.-a). *Managing secrets when deploying your app.*
https://docs.streamlit.io/deploy/concepts/secrets

Streamlit. (s. f.-b). *st.login.*
https://docs.streamlit.io/develop/api-reference/user/st.login

Streamlit. (s. f.-c). *User authentication and information.*
https://docs.streamlit.io/develop/concepts/connections/authentication

Wiggins, A. (2017). *The twelve-factor app.* https://12factor.net/

