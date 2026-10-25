-- 集集斗六生態調查資料庫 schema (Phase 1 範圍：斗六堰歷年資料)
-- 資料庫引擎：PostgreSQL (plain, no extensions required)

CREATE TABLE IF NOT EXISTS fact_species_count (
    id                  BIGSERIAL PRIMARY KEY,
    station             TEXT,
    survey_date         DATE,
    survey_date_roc     TEXT,
    year                INTEGER NOT NULL,
    season              INTEGER,
    count               INTEGER NOT NULL,
    species_name_zh     TEXT,
    species_name_latin  TEXT,
    category            TEXT,           -- 魚 / 蝦 / 爬蟲
    order_name          TEXT,
    family_name         TEXT,
    trait               TEXT,           -- 原生種 / 外來種 等
    habitat             TEXT            -- 游泳性 / 底棲性 等
);
CREATE INDEX IF NOT EXISTS idx_fsc_year ON fact_species_count(year);
CREATE INDEX IF NOT EXISTS idx_fsc_station ON fact_species_count(station);
CREATE INDEX IF NOT EXISTS idx_fsc_species ON fact_species_count(species_name_latin);
CREATE INDEX IF NOT EXISTS idx_fsc_category ON fact_species_count(category);

CREATE TABLE IF NOT EXISTS fact_specimen_hosp (
    id                  BIGSERIAL PRIMARY KEY,
    capture_date        DATE,
    capture_date_roc    TEXT,
    station             TEXT,
    body_length_cm      NUMERIC,
    total_length_cm     NUMERIC,
    weight_g            NUMERIC,
    stomach_algae       TEXT,
    stomach_debris      TEXT,
    stomach_bugs        TEXT,
    stomach_fish_tissue TEXT,
    egg_mature          TEXT,
    egg_immature        TEXT,
    testis_mature       TEXT
);
-- 何氏棘鲃 (Spinibarbus hollandi)為保育類指標物種的個體量測紀錄，
-- 目前僅涵蓋 2026 年(資料來源檔案本身只保留當年度記錄，歷史年度需另行補登)

CREATE TABLE IF NOT EXISTS fact_conservation_species (
    id                      BIGSERIAL PRIMARY KEY,
    period_label            TEXT NOT NULL,   -- 原始檔案的期間標示，例如 "2022.全年"
    order_name              TEXT,
    family_name             TEXT,
    species_name_latin      TEXT NOT NULL,
    endemic_status          TEXT,
    conservation_grade      TEXT,
    station_upstream        INTEGER,
    station_fishway         INTEGER,
    station_fishway_entrance INTEGER,
    station_downstream      INTEGER,
    total                   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_fcs_period ON fact_conservation_species(period_label);

CREATE TABLE IF NOT EXISTS fact_water_quality (
    id                      BIGSERIAL PRIMARY KEY,
    sample_date             DATE,
    sample_time             TEXT,
    air_temp_c              NUMERIC,
    water_temp_c            NUMERIC,
    ph                      NUMERIC,
    conductivity_umho_cm25c NUMERIC,
    dissolved_oxygen_mgl    NUMERIC,
    bod_mgl                 NUMERIC,
    cod_mgl                 NUMERIC,
    ss_mgl                  NUMERIC
);
CREATE INDEX IF NOT EXISTS idx_fwq_date ON fact_water_quality(sample_date);

-- 方便 BI 查詢的彙總視圖：每年度各物種分類的總數量與測站數
CREATE OR REPLACE VIEW v_species_year_summary AS
SELECT year, category, species_name_latin, species_name_zh,
       SUM(count) AS total_count, COUNT(DISTINCT station) AS station_count,
       COUNT(DISTINCT survey_date) AS survey_count
FROM fact_species_count
GROUP BY year, category, species_name_latin, species_name_zh;

CREATE OR REPLACE VIEW v_category_year_trend AS
SELECT year, category, SUM(count) AS total_count
FROM fact_species_count
GROUP BY year, category
ORDER BY year, category;

CREATE OR REPLACE VIEW v_station_year_trend AS
SELECT year, station, SUM(count) AS total_count
FROM fact_species_count
WHERE station IS NOT NULL
GROUP BY year, station
ORDER BY year, station;
