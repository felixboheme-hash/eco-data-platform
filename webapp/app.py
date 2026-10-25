# -*- coding: utf-8 -*-
"""斗六堰生態調查資料 BI API + 靜態前端。FastAPI + Postgres。"""
import os
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, List

app = FastAPI(title="斗六堰生態調查 BI API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_conn():
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "eco_data_platform"),
        user=os.environ.get("PGUSER", "eco"),
        password=os.environ.get("PGPASSWORD", "eco"),
    )


def query(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/api/summary")
def summary():
    r = query("""
        SELECT COUNT(*) AS total_records,
               COUNT(DISTINCT species_name_latin) AS species_count,
               COUNT(DISTINCT station) AS station_count,
               MIN(year) AS min_year, MAX(year) AS max_year,
               SUM(count) AS total_individuals
        FROM fact_species_count
    """)
    return r[0]


@app.get("/api/filters")
def filters():
    species = query("SELECT DISTINCT species_name_latin, species_name_zh, category FROM fact_species_count WHERE species_name_latin IS NOT NULL ORDER BY category, species_name_latin")
    stations = query("SELECT DISTINCT station FROM fact_species_count WHERE station IS NOT NULL ORDER BY station")
    years = query("SELECT DISTINCT year FROM fact_species_count ORDER BY year")
    categories = query("SELECT DISTINCT category FROM fact_species_count WHERE category IS NOT NULL ORDER BY category")
    return {
        "species": species, "stations": [s["station"] for s in stations],
        "years": [y["year"] for y in years], "categories": [c["category"] for c in categories],
    }


@app.get("/api/trend/category")
def trend_category(station: Optional[str] = None, year_from: Optional[int] = None, year_to: Optional[int] = None):
    conds, params = [], []
    if station:
        conds.append("station = %s"); params.append(station)
    if year_from:
        conds.append("year >= %s"); params.append(year_from)
    if year_to:
        conds.append("year <= %s"); params.append(year_to)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return query(f"""
        SELECT year, category, SUM(count) AS total_count
        FROM fact_species_count {where}
        GROUP BY year, category ORDER BY year, category
    """, params)


@app.get("/api/trend/station")
def trend_station(category: Optional[str] = None, year_from: Optional[int] = None, year_to: Optional[int] = None):
    conds, params = ["station IS NOT NULL"], []
    if category:
        conds.append("category = %s"); params.append(category)
    if year_from:
        conds.append("year >= %s"); params.append(year_from)
    if year_to:
        conds.append("year <= %s"); params.append(year_to)
    where = "WHERE " + " AND ".join(conds)
    return query(f"""
        SELECT year, station, SUM(count) AS total_count
        FROM fact_species_count {where}
        GROUP BY year, station ORDER BY year, station
    """, params)


@app.get("/api/top_species")
def top_species(category: Optional[str] = None, year_from: Optional[int] = None, year_to: Optional[int] = None, limit: int = 15):
    conds, params = ["species_name_latin IS NOT NULL"], []
    if category:
        conds.append("category = %s"); params.append(category)
    if year_from:
        conds.append("year >= %s"); params.append(year_from)
    if year_to:
        conds.append("year <= %s"); params.append(year_to)
    where = "WHERE " + " AND ".join(conds)
    params.append(limit)
    return query(f"""
        SELECT species_name_latin, species_name_zh, category, SUM(count) AS total_count
        FROM fact_species_count {where}
        GROUP BY species_name_latin, species_name_zh, category
        ORDER BY total_count DESC LIMIT %s
    """, params)


@app.get("/api/species_trend")
def species_trend(species_name_latin: str, station: Optional[str] = None):
    conds, params = ["species_name_latin = %s"], [species_name_latin]
    if station:
        conds.append("station = %s"); params.append(station)
    where = "WHERE " + " AND ".join(conds)
    return query(f"""
        SELECT year, SUM(count) AS total_count
        FROM fact_species_count {where}
        GROUP BY year ORDER BY year
    """, params)


@app.get("/api/conservation")
def conservation():
    return query("""
        SELECT period_label, species_name_latin, conservation_grade, endemic_status, total
        FROM fact_conservation_species
        ORDER BY id DESC LIMIT 200
    """)


@app.get("/api/water_quality")
def water_quality():
    return query("SELECT * FROM fact_water_quality ORDER BY sample_date")


@app.get("/api/specimen_hosp")
def specimen_hosp():
    return query("SELECT * FROM fact_specimen_hosp ORDER BY capture_date")


@app.get("/health")
def health():
    return {"status": "ok"}


# 靜態前端 (Power BI / Tableau 風格的分析頁面)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
