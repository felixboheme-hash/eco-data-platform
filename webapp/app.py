# -*- coding: utf-8 -*-
"""斗六堰生態調查資料 BI API + 靜態前端。FastAPI + Postgres。"""
import os
import re
import hmac
import time
import hashlib
import secrets
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="斗六堰生態調查 BI API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---- 帳號 / 登入設定 ----
# 帳號資料表與初始管理員由 Liquibase 建立（liquibase/changelog/），webapp 不建表。
SESSION_COOKIE = "eco_session"
SESSION_HOURS = 12
# 雜湊格式 pbkdf2_sha256$<次數>$<salt hex>$<hash hex>；次數存在每筆雜湊內，日後調高不影響舊密碼驗證
PBKDF2_ITERATIONS = 600_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD_LEN = 6
# 不需登入即可存取的路徑
PUBLIC_PATHS = {"/login.html", "/api/login", "/health", "/favicon.ico"}


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


def execute(sql, params=None):
    """執行寫入語句並 commit；有 RETURNING 時回傳結果列。"""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or [])
            rows = cur.fetchall() if cur.description else []
        conn.commit()
        return rows
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 帳號管理 / 登入
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except ValueError:
        return False


def token_hash(token: str) -> str:
    # 資料庫只存 session token 的雜湊，資料庫外洩也無法直接冒用登入狀態
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_user(token: Optional[str]):
    if not token:
        return None
    rows = query("""
        SELECT u.id, u.username, u.is_admin
        FROM app_session s JOIN app_user u ON u.id = s.user_id
        WHERE s.token_hash = %s AND s.expires_at > now()
    """, [token_hash(token)])
    return rows[0] if rows else None


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS:
        return await call_next(request)
    user = await run_in_threadpool(session_user, request.cookies.get(SESSION_COOKIE))
    if user is None:
        if path.startswith("/api/"):
            return JSONResponse({"detail": "未登入或登入已逾時"}, status_code=401)
        return RedirectResponse("/login.html", status_code=303)
    request.state.user = user
    response = await call_next(request)
    # 需登入的內容不可直接用瀏覽器快取，否則登出後仍可看到舊頁面；no-cache 仍可用 ETag 回 304，不會重複下載
    response.headers["Cache-Control"] = "private, no-cache"
    return response


def require_admin(request: Request):
    if not request.state.user["is_admin"]:
        raise HTTPException(status_code=403, detail="需要管理員權限")


def validate_password(password: str):
    if len(password) < MIN_PASSWORD_LEN:
        raise HTTPException(status_code=400, detail=f"密碼至少需 {MIN_PASSWORD_LEN} 個字元")


def admin_count():
    return query("SELECT COUNT(*) AS n FROM app_user WHERE is_admin")[0]["n"]


class LoginBody(BaseModel):
    username: str
    password: str


class ChangePasswordBody(BaseModel):
    old_password: str
    new_password: str


class NewUserBody(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class UpdateUserBody(BaseModel):
    password: Optional[str] = None
    is_admin: Optional[bool] = None


@app.post("/api/login")
def login(body: LoginBody):
    rows = query("SELECT id, password_hash FROM app_user WHERE username = %s", [body.username.strip()])
    if not rows or not verify_password(body.password, rows[0]["password_hash"]):
        time.sleep(1)  # 降低暴力猜密碼的速度
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    token = secrets.token_urlsafe(32)
    execute("DELETE FROM app_session WHERE expires_at <= now()")
    execute("INSERT INTO app_session (token_hash, user_id, expires_at) VALUES (%s, %s, now() + %s * interval '1 hour')",
            [token_hash(token), rows[0]["id"], SESSION_HOURS])
    resp = JSONResponse({"ok": True})
    resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_HOURS * 3600, httponly=True, samesite="lax")
    return resp


@app.post("/api/logout")
def logout(request: Request):
    execute("DELETE FROM app_session WHERE token_hash = %s", [token_hash(request.cookies.get(SESSION_COOKIE, ""))])
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/api/me")
def me(request: Request):
    return request.state.user


@app.post("/api/me/password")
def change_own_password(request: Request, body: ChangePasswordBody):
    user = request.state.user
    stored = query("SELECT password_hash FROM app_user WHERE id = %s", [user["id"]])[0]["password_hash"]
    if not verify_password(body.old_password, stored):
        raise HTTPException(status_code=400, detail="目前密碼不正確")
    validate_password(body.new_password)
    execute("UPDATE app_user SET password_hash = %s WHERE id = %s", [hash_password(body.new_password), user["id"]])
    # 其他裝置上的登入一律失效，保留目前這一個
    execute("DELETE FROM app_session WHERE user_id = %s AND token_hash <> %s",
            [user["id"], token_hash(request.cookies.get(SESSION_COOKIE, ""))])
    return {"ok": True}


@app.get("/api/users")
def list_users(request: Request):
    require_admin(request)
    return query("SELECT id, username, is_admin, created_at FROM app_user ORDER BY id")


@app.post("/api/users")
def create_user(request: Request, body: NewUserBody):
    require_admin(request)
    username = body.username.strip()
    if not USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="帳號需為 3-32 個英數字或 _ . -")
    validate_password(body.password)
    rows = execute("INSERT INTO app_user (username, password_hash, is_admin) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING RETURNING id",
                   [username, hash_password(body.password), body.is_admin])
    if not rows:
        raise HTTPException(status_code=400, detail="帳號已存在")
    return {"ok": True, "id": rows[0]["id"]}


@app.put("/api/users/{user_id}")
def update_user(request: Request, user_id: int, body: UpdateUserBody):
    require_admin(request)
    target = query("SELECT id, is_admin FROM app_user WHERE id = %s", [user_id])
    if not target:
        raise HTTPException(status_code=404, detail="找不到此帳號")
    if body.is_admin is not None and body.is_admin != target[0]["is_admin"]:
        if user_id == request.state.user["id"]:
            raise HTTPException(status_code=400, detail="不能變更自己的管理員權限")
        if not body.is_admin and admin_count() <= 1:
            raise HTTPException(status_code=400, detail="至少需保留一個管理員")
        execute("UPDATE app_user SET is_admin = %s WHERE id = %s", [body.is_admin, user_id])
    if body.password:
        validate_password(body.password)
        execute("UPDATE app_user SET password_hash = %s WHERE id = %s", [hash_password(body.password), user_id])
        # 密碼被管理員重設後，該帳號原有的登入一律失效
        execute("DELETE FROM app_session WHERE user_id = %s", [user_id])
    return {"ok": True}


@app.delete("/api/users/{user_id}")
def delete_user(request: Request, user_id: int):
    require_admin(request)
    if user_id == request.state.user["id"]:
        raise HTTPException(status_code=400, detail="不能刪除自己的帳號")
    target = query("SELECT is_admin FROM app_user WHERE id = %s", [user_id])
    if not target:
        raise HTTPException(status_code=404, detail="找不到此帳號")
    if target[0]["is_admin"] and admin_count() <= 1:
        raise HTTPException(status_code=400, detail="至少需保留一個管理員")
    execute("DELETE FROM app_user WHERE id = %s", [user_id])
    return {"ok": True}


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


# 登入頁與帳號管理頁打包在映像檔內（auth_pages/），不受 docker-compose 把 static/ 換成 artifact_data/ 掛載的影響
AUTH_PAGES_DIR = os.path.join(os.path.dirname(__file__), "auth_pages")


@app.get("/login.html", include_in_schema=False)
def login_page():
    return FileResponse(os.path.join(AUTH_PAGES_DIR, "login.html"))


@app.get("/account.html", include_in_schema=False)
def account_page():
    return FileResponse(os.path.join(AUTH_PAGES_DIR, "account.html"))


# 靜態前端 (Power BI / Tableau 風格的分析頁面)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
