# -*- coding: utf-8 -*-
"""將 data/*.csv 匯入 PostgreSQL。於 etl 容器內執行，或在有 psycopg2 的環境中直接執行。
連線資訊讀取環境變數：PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD (docker-compose 已設定好)。
"""
import os
import time
import csv
import psycopg2

# 容器內路徑對應 docker-compose.yml 的 volume 掛載 (./sql:/app/sql, ./data:/app/data)；
# 若直接在本機執行(非容器)，可用環境變數 DATA_DIR / SCHEMA_SQL 覆寫。
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
SCHEMA_SQL = os.environ.get("SCHEMA_SQL", "/app/sql/schema.sql")
if not os.path.exists(SCHEMA_SQL):
    # 本機（非容器）執行時的備援路徑
    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
    SCHEMA_SQL = os.path.join(os.path.dirname(__file__), "..", "sql", "schema.sql")

TABLES = {
    "fact_species_count": ["station", "survey_date", "survey_date_roc", "year", "season", "count",
                            "species_name_zh", "species_name_latin", "category", "order_name",
                            "family_name", "trait", "habitat"],
    "fact_specimen_hosp": ["capture_date", "capture_date_roc", "station", "body_length_cm",
                           "total_length_cm", "weight_g", "stomach_algae", "stomach_debris",
                           "stomach_bugs", "stomach_fish_tissue", "egg_mature", "egg_immature",
                           "testis_mature"],
    "fact_conservation_species": ["period_label", "order_name", "family_name", "species_name_latin",
                                  "endemic_status", "conservation_grade", "station_upstream",
                                  "station_fishway", "station_fishway_entrance", "station_downstream",
                                  "total"],
    "fact_water_quality": ["sample_date", "sample_time", "air_temp_c", "water_temp_c", "ph",
                           "conductivity_umho_cm25c", "dissolved_oxygen_mgl", "bod_mgl", "cod_mgl", "ss_mgl"],
}


def wait_for_db(conn_kwargs, retries=30, delay=2):
    for i in range(retries):
        try:
            conn = psycopg2.connect(**conn_kwargs)
            conn.close()
            return
        except Exception as e:
            print(f"[{i+1}/{retries}] waiting for postgres... ({e})")
            time.sleep(delay)
    raise RuntimeError("Postgres not reachable")


def main():
    conn_kwargs = dict(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "eco_data_platform"),
        user=os.environ.get("PGUSER", "eco"),
        password=os.environ.get("PGPASSWORD", "eco"),
    )
    wait_for_db(conn_kwargs)
    conn = psycopg2.connect(**conn_kwargs)
    conn.autocommit = True
    cur = conn.cursor()

    with open(SCHEMA_SQL, encoding="utf-8") as f:
        cur.execute(f.read())
    print("schema applied")

    for table, cols in TABLES.items():
        csv_path = os.path.join(DATA_DIR, f"{table}.csv")
        if not os.path.exists(csv_path):
            print(f"skip {table}: {csv_path} not found")
            continue
        cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY")
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if not rows:
            print(f"{table}: 0 rows, skipped")
            continue
        col_list = ",".join(cols)
        placeholders = ",".join(["%s"] * len(cols))
        insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
        batch = [[ (r[c] if r[c] != "" else None) for c in cols] for r in rows]
        cur.executemany(insert_sql, batch)
        print(f"{table}: loaded {len(batch)} rows")

    cur.close()
    conn.close()
    print("ETL complete")


if __name__ == "__main__":
    main()
