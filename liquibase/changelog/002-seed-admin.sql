--liquibase formatted sql

--changeset eco:002-seed-admin
--comment: 初始管理員 labtcs（只存 PBKDF2 雜湊）。只執行一次；帳號已存在時不覆蓋。首次登入後請到「帳號管理」修改密碼。
INSERT INTO app_user (username, password_hash, is_admin)
VALUES ('labtcs', 'pbkdf2_sha256$600000$eb9909e60f0bf1b096fbc6ae969df29f$edde072bcb9885bb370cfc1cbd932941628fd1214d8f1da501aaf810ef790eba', TRUE)
ON CONFLICT (username) DO NOTHING;
--rollback DELETE FROM app_user WHERE username = 'labtcs';
