-- Esquema mínimo de datos (guía, sección 7.3.1).
-- SQLite. Todas las tablas usan claves suficientes para las
-- transacciones atómicas que exige RF-02.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS preconsent_flows (
    flow_id_hash    TEXT PRIMARY KEY,   -- sha256 del flow_id opaco entregado al navegador
    disclaimer_version TEXT NOT NULL,
    privacy_version     TEXT NOT NULL,
    accepted_at     TEXT NOT NULL,      -- ISO8601 UTC
    expires_at      TEXT NOT NULL,      -- accepted_at + 15 minutos
    consumed_at     TEXT                -- NULL hasta que el callback OIDC lo consume
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id         TEXT PRIMARY KEY,   -- uuid generado localmente
    issuer          TEXT NOT NULL,
    subject         TEXT NOT NULL,
    provider        TEXT NOT NULL,      -- 'google' | 'microsoft'
    display_name    TEXT NOT NULL,
    email           TEXT NOT NULL,
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    purge_at        TEXT,
    UNIQUE(issuer, subject)
);

CREATE TABLE IF NOT EXISTS consent_events (
    consent_id      TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES profiles(user_id),
    kind            TEXT NOT NULL CHECK (kind IN ('privacy', 'disclaimer', 'revocation')),
    version         TEXT NOT NULL,
    status          TEXT NOT NULL,      -- 'accepted' | 'revoked'
    occurred_at     TEXT NOT NULL,
    method          TEXT NOT NULL,      -- 'checkbox_explicit'
    preconsent_id   TEXT NOT NULL REFERENCES preconsent_flows(flow_id_hash)
);

CREATE TABLE IF NOT EXISTS app_sessions (
    session_id          TEXT PRIMARY KEY,
    user_id              TEXT NOT NULL REFERENCES profiles(user_id),
    idp_iat              TEXT,               -- issued_at del token OIDC, si disponible
    created_at           TEXT NOT NULL,
    last_seen_at         TEXT NOT NULL,
    absolute_expires_at  TEXT NOT NULL,      -- created_at + 8 horas
    status               TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'closed'
    closed_at            TEXT
);

-- Una única sesión activa por usuario (RF-02, punto 64).
CREATE UNIQUE INDEX IF NOT EXISTS ux_app_sessions_active_user
    ON app_sessions(user_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS auth_events (
    event_id        TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES profiles(user_id),
    session_id      TEXT NOT NULL REFERENCES app_sessions(session_id),
    event_type      TEXT NOT NULL,      -- 'session_started' | 'logout' | 'expired'
    result          TEXT NOT NULL,      -- 'success' | 'rejected'
    occurred_at     TEXT NOT NULL,
    app_version     TEXT NOT NULL,
    purge_at        TEXT
);

CREATE TABLE IF NOT EXISTS notification_outbox (
    outbox_id       TEXT PRIMARY KEY,
    event_id        TEXT NOT NULL REFERENCES auth_events(event_id),
    session_id      TEXT NOT NULL REFERENCES app_sessions(session_id),
    type            TEXT NOT NULL,      -- 'session_started'
    destination_alias TEXT NOT NULL,    -- alias institucional, nunca correo real de tercero
    status          TEXT NOT NULL DEFAULT 'pending',  -- 'pending'|'sent'|'failed'
    attempt_count   INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL,
    error           TEXT,
    sent_at         TEXT,
    purge_at        TEXT,
    UNIQUE(session_id, type)
);

CREATE TABLE IF NOT EXISTS deletion_markers (
    marker_hmac     TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    reason          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    last_reapplied_at TEXT
);

CREATE TABLE IF NOT EXISTS lifecycle_jobs (
    job_id          TEXT PRIMARY KEY,
    reason          TEXT NOT NULL,
    scheduled_at    TEXT NOT NULL,
    executed_at     TEXT,
    status          TEXT NOT NULL DEFAULT 'scheduled',
    deleted_counts  TEXT
);
