--liquibase formatted sql

--changeset eco:001-auth-tables
--comment: 帳號與登入 session 資料表（由 webapp 使用；不在 sql/schema.sql，ETL 重新匯入資料不影響帳號）
CREATE TABLE IF NOT EXISTS app_user (
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,          -- pbkdf2_sha256$<次數>$<salt hex>$<hash hex>，不存明碼
    is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS app_session (
    token_hash TEXT PRIMARY KEY,          -- session token 的 SHA-256，不存原始 token
    user_id    BIGINT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL
);
--rollback DROP TABLE app_session; DROP TABLE app_user;
