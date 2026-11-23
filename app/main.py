import os, string, random, time
import importlib
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI()

DB_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/url_shortener")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
USE_CACHE = os.getenv("USE_CACHE", "true").lower() == "true"

try:
    redis = importlib.import_module("redis")
except ModuleNotFoundError:
    redis = None
    USE_CACHE = False

cache = redis.Redis.from_url(REDIS_URL, decode_responses=True) if USE_CACHE else None

def get_db():
    psycopg2 = importlib.import_module("psycopg2")
    return psycopg2.connect(DB_URL)

@app.on_event("startup")
def init_db():

    for _ in range(5):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS urls (
                    id SERIAL PRIMARY KEY,
                    short_url VARCHAR(10) UNIQUE NOT NULL,
                    original_url TEXT NOT NULL
                );
            """)

            conn.commit()
            cur.close()
            conn.close()
            break
        except Exception:
            time.sleep(2)

class URLRequest(BaseModel):
    url: str

def generate_code(length=6):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length)) 

@app.post("/shorten")
def shortn_url(req: URLRequest):
    code = generate_code()
    conn = get_db()
    cur = conn.cursor()   
    cur.execute("INSERT INTO urls (short_url, original_url) VALUES (%s, %s) RETURNING short_url", (code, req.url))
    conn.commit()
    cur.close()
    conn.close()
    return {"short_url":f"http://localhost:8000/{code}","code":code}

@app.post("/seed/{count}")
def seed_data(count: int):
    conn = get_db()
    cur = conn.cursor()
    # Generate data dummy cepat menggunakan execute_values atau loop batch
    records = [(f"code{i}", f"https://example.com/artikel-panjang-ke-{i}") for i in range(count)]
    args_str = ','.join(cur.mogrify("(%s,%s)", x).decode('utf-8') for x in records)
    cur.execute("INSERT INTO urls (short_code, original_url) VALUES " + args_str)
    conn.commit()
    cur.close()
    conn.close()
    return {"status": f"Berhasil mengisi {count} baris data dummy"}

@app.get("/{code}")
def redirect_url(code: str):
    # 1. Cek Redis Cache jika fitur diaktifkan (Cache-Aside Pattern)
    if USE_CACHE:
        cached_url = cache.get(f"url:{code}")
        if cached_url:
            return RedirectResponse(url=cached_url, status_code=302)

    # 2. Query ke PostgreSQL (Cache Miss atau Cache Mati)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT original_url FROM urls WHERE short_code = %s", (code,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="URL tidak ditemukan")

    original_url = row[0]

    # 3. Simpan ke Redis dengan TTL 1 jam (3600 detik)
    if USE_CACHE:
        cache.setex(f"url:{code}", 3600, original_url)

    return RedirectResponse(url=original_url, status_code=302)