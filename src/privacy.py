"""Aviso de privacidad (sección 3.3 de la guía).

Debe presentarse como control separado y no premarcado respecto del
disclaimer académico, antes de redirigir a Google/Microsoft.
"""

PRIVACY_NOTICE_VERSION = "1.0"

PRIVACY_NOTICE_TEXT = (
    "Datos tratados: identificador de proveedor (issuer, subject), "
    "nombre y correo de la cuenta autenticada mediante Google o "
    "Microsoft (OIDC). No se solicitan ni almacenan contraseñas, "
    "tokens de acceso ni tokens de refresco.\n\n"
    "Finalidad: identificar de forma única a cada usuario del piloto "
    "académico, generar el evento de auditoría de acceso y habilitar "
    "las funciones analíticas del sistema.\n\n"
    "Responsable y restricción del piloto: equipo del curso Teoría "
    "Moderna de Portafolios (Tech Business School - Universidad EIA). "
    "El acceso está restringido a cuentas ficticias autorizadas por el "
    "docente; no hay registro abierto ni usuarios reales.\n\n"
    "Destinatario institucional: los eventos de notificación se "
    "envían únicamente al sink institucional del curso, nunca a "
    "terceros externos.\n\n"
    "Conservación: los datos se conservan durante el periodo de "
    "evaluación y se eliminan a más tardar 90 días después de la "
    "firmeza de la calificación, o antes si el usuario solicita la "
    "eliminación.\n\n"
    "Procedimiento de eliminación: al cierre del piloto o por "
    "solicitud válida, un proceso de ciclo de vida (lifecycle_worker) "
    "purga perfil, consentimientos, sesiones, eventos y notificaciones "
    "asociadas.\n\n"
    "Canal de contacto: a través del docente responsable del curso, "
    "Julián Esteban Restrepo Montoya."
)
