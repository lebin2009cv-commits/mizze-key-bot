import sqlite3
import secrets
import string
import os
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ⚠️ KHAI BÁO LINK Ở ĐÂY (Sau này muốn đổi link, chỉ cần sửa ở đây)
SHORT_LINKS = [
    "https://link4m.net/go/HEDP6k5i", 
    "https://link4m.net/go/djYtu", 
    "https://link4m.net/go/djYtu", 
    "https://link4m.org/go/hWucf"  
]

def init_db():
    conn = sqlite3.connect("keys.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS key_prices (id INTEGER PRIMARY KEY, name TEXT, duration_days REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS keys (id INTEGER PRIMARY KEY, key_code TEXT UNIQUE, user_id INTEGER, plan_id INTEGER, expires_at TIMESTAMP, is_activated BOOLEAN DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS passes (token TEXT PRIMARY KEY, user_id INTEGER, used BOOLEAN DEFAULT 0)''')
    
    c.execute("INSERT OR IGNORE INTO key_prices (id, name, duration_days) VALUES (3, 'Key 6 Giờ', 0.25)")
    c.execute("INSERT OR IGNORE INTO key_prices (id, name, duration_days) VALUES (4, 'Key 3 Giờ', 0.125)")
    conn.commit()
    conn.close()

def gen_key():
    return "-".join("".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4)) for _ in range(3))

@app.get("/")
def home():
    return {"status": "Backend & Bot is running 24/7!"}

# API LẤY DANH SÁCH LINK (Dành cho app.js)
@app.get("/api/get_links")
def get_links():
    return {"status": "success", "links": SHORT_LINKS}

@app.get("/get_pass")
def get_pass(user_id: int):
    conn = sqlite3.connect("keys.db")
    token = secrets.token_hex(8)
    conn.execute("INSERT INTO passes (token, user_id, used) VALUES (?, ?, 0)", (token, user_id))
    conn.commit()
    conn.close()
    return {"status": "success", "pass_token": token}

@app.post("/claim_key")
def claim_key(user_id: int, plan: str, tokens: str):
    token_list = tokens.split(",")
    required_passes = 4 if plan == "6h" else 3
    
    if len(token_list) < required_passes:
        raise HTTPException(status_code=400, detail="Chưa đủ số lượng vé")
        
    conn = sqlite3.connect("keys.db")
    
    for t in token_list:
        v = conn.execute("SELECT used FROM passes WHERE token=? AND user_id=?", (t, user_id)).fetchone()
        if not v or v[0] == 1:
            conn.close()
            raise HTTPException(status_code=400, detail="Vé không hợp lệ hoặc đã dùng. Hãy làm lại!")
            
    for t in token_list:
        conn.execute("UPDATE passes SET used=1 WHERE token=?", (t,))
        
    plan_id = 3 if plan == "6h" else 4
    code = gen_key()
    
    conn.execute("INSERT INTO keys (key_code, user_id, plan_id, expires_at, is_activated) VALUES (?, ?, ?, NULL, 0)", (code, user_id, plan_id))
    conn.commit()
    conn.close()
    
    return {"status": "success", "key": code}

@app.get("/activate_key")
def activate_key(key_code: str):
    conn = sqlite3.connect("keys.db")
    k = conn.execute("SELECT id, plan_id, is_activated FROM keys WHERE key_code=?", (key_code,)).fetchone()
    if not k:
        conn.close()
        raise HTTPException(status_code=404, detail="Key không tồn tại")
    if k[2] == 1:
        conn.close()
        raise HTTPException(status_code=400, detail="Key này đã được kích hoạt!")
        
    p = conn.execute("SELECT duration_days FROM key_prices WHERE id=?", (k[1],)).fetchone()
    expires = datetime.now() + timedelta(days=p[0])
    conn.execute("UPDATE keys SET is_activated=1, expires_at=? WHERE id=?", (expires, k[0]))
    conn.commit()
    conn.close()
    return {"status": "success", "expires": expires.strftime('%d/%m/%Y %H:%M')}

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)