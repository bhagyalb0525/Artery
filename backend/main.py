"""
Digital Art Marketplace — Backend
A single-file FastAPI app: auth, artwork upload, browsing, and purchase.
Database: PostgreSQL (via psycopg2)

Run:
    pip install -r requirements.txt
    python main.py
"""

import os
import shutil
import uuid
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List

import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
import razorpay
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from jose import jwt, JWTError

# ----------------------------------------------------------------------------
# Config — loaded from a .env file (see .env.example for the template)
# ----------------------------------------------------------------------------

load_dotenv(override=True)  # reads variables from a .env file in the same folder into os.environ

# Most free Postgres hosts (Neon, Supabase, Render, Railway) hand you a single
# connection string instead of separate host/user/password fields. We support
# both: if DATABASE_URL is set, use it directly; otherwise build one from the
# individual DB_* vars (handy for local dev against a local Postgres install).
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "art_marketplace")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Neon/Supabase/Render Postgres all require SSL for external connections.
# sslmode=require is harmless for local dev too (local Postgres just won't
# get this param unless you add it to DATABASE_URL yourself).
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set. Create a .env file (see .env.example) "
        "and set SECRET_KEY to a long random string."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

# CORS — comma-separated list of allowed frontend origins (set in .env)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# --- Razorpay (test mode keys — get these from https://dashboard.razorpay.com/app/keys) ---
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    raise RuntimeError(
        "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not set. Sign up at razorpay.com, "
        "grab your TEST mode keys from the dashboard, and add them to .env."
    )

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)

# ----------------------------------------------------------------------------
# DB connection pool
# ----------------------------------------------------------------------------

pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1, maxconn=5, dsn=DATABASE_URL, sslmode=DB_SSLMODE
)


def get_db():
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


def init_db():
    """Creates tables if they don't already exist. Run once on startup."""
    conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS artworks (
            id SERIAL PRIMARY KEY,
            title VARCHAR(150) NOT NULL,
            description TEXT,
            price DECIMAL(10, 2) NOT NULL,
            category VARCHAR(50) DEFAULT 'other',
            image_path VARCHAR(255) NOT NULL,
            artist_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            stock INT NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            buyer_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            artwork_id INT NOT NULL REFERENCES artworks(id) ON DELETE CASCADE,
            amount DECIMAL(10, 2) NOT NULL,
            razorpay_order_id VARCHAR(100) UNIQUE NOT NULL,
            razorpay_payment_id VARCHAR(100),
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


# ----------------------------------------------------------------------------
# Pydantic schemas
# ----------------------------------------------------------------------------

class UserSignup(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ArtworkOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    price: float
    category: str
    image_path: str
    artist_id: int
    stock: int = 1
    artist_name: Optional[str] = None
    created_at: Optional[str] = None


class VerifyPayment(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


# ----------------------------------------------------------------------------
# Auth helpers
# ----------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    if token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, name, email FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    if user is None:
        raise credentials_exception
    return user


# ----------------------------------------------------------------------------
# App setup
# ----------------------------------------------------------------------------

app = FastAPI(title="Digital Art Marketplace API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # set via ALLOWED_ORIGINS in .env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded images at /static/uploads/<filename>
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "static")), name="static")


@app.on_event("startup")
def on_startup():
    init_db()


# ----------------------------------------------------------------------------
# Auth routes
# ----------------------------------------------------------------------------

@app.post("/signup", status_code=201)
def signup(user: UserSignup, db=Depends(get_db)):
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id FROM users WHERE email = %s", (user.email,))
    if cur.fetchone():
        cur.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = hash_password(user.password)
    cur.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
        (user.name, user.email, hashed),
    )
    new_id = cur.fetchone()["id"]
    db.commit()
    cur.close()

    token = create_access_token({"user_id": new_id})
    return {"access_token": token, "token_type": "bearer", "name": user.name}


@app.post("/login")
def login(credentials: UserLogin, db=Depends(get_db)):
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE email = %s", (credentials.email,))
    user = cur.fetchone()
    cur.close()

    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token({"user_id": user["id"]})
    return {"access_token": token, "token_type": "bearer", "name": user["name"]}


@app.get("/me")
def read_current_user(current_user=Depends(get_current_user)):
    return current_user


# ----------------------------------------------------------------------------
# Artwork routes — browsing is public, uploading/buying needs auth
# ----------------------------------------------------------------------------

@app.get("/artworks", response_model=List[ArtworkOut])
def browse_artworks(category: Optional[str] = None, search: Optional[str] = None, db=Depends(get_db)):
    """Public endpoint — anyone can browse the gallery, with optional filters."""
    cur = db.cursor(cursor_factory=RealDictCursor)
    query = """
        SELECT a.id, a.title, a.description, a.price, a.category,
               a.image_path, a.artist_id, a.stock, u.name AS artist_name, a.created_at
        FROM artworks a
        JOIN users u ON a.artist_id = u.id
        WHERE 1=1
    """
    params = []
    if category and category != "all":
        query += " AND a.category = %s"
        params.append(category)
    if search:
        # ILIKE = Postgres's case-insensitive LIKE (MySQL's LIKE is
        # case-insensitive by default on most default collations, so this
        # keeps the same user-facing behaviour).
        query += " AND a.title ILIKE %s"
        params.append(f"%{search}%")
    query += " ORDER BY a.created_at DESC"

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    cur.close()

    for r in rows:
        r["created_at"] = str(r["created_at"])
    return rows


@app.get("/artworks/{artwork_id}", response_model=ArtworkOut)
def get_artwork(artwork_id: int, db=Depends(get_db)):
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT a.id, a.title, a.description, a.price, a.category,
               a.image_path, a.artist_id, a.stock, u.name AS artist_name, a.created_at
        FROM artworks a
        JOIN users u ON a.artist_id = u.id
        WHERE a.id = %s
    """, (artwork_id,))
    art = cur.fetchone()
    cur.close()
    if not art:
        raise HTTPException(status_code=404, detail="Artwork not found")
    art["created_at"] = str(art["created_at"])
    return art


@app.post("/artworks", status_code=201)
def upload_artwork(
    title: str = Form(...),
    description: str = Form(""),
    price: float = Form(...),
    category: str = Form("other"),
    stock: int = Form(1),
    image: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Authenticated artists upload new artwork with an image file."""
    ext = os.path.splitext(image.filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        raise HTTPException(status_code=400, detail="Unsupported image format")

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """INSERT INTO artworks (title, description, price, category, image_path, artist_id, stock)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (title, description, price, category, f"/static/uploads/{filename}", current_user["id"], stock),
    )
    new_id = cur.fetchone()["id"]
    db.commit()
    cur.close()
    return {"id": new_id, "message": "Artwork uploaded successfully"}


@app.delete("/artworks/{artwork_id}")
def delete_artwork(artwork_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM artworks WHERE id = %s", (artwork_id,))
    art = cur.fetchone()
    if not art:
        cur.close()
        raise HTTPException(status_code=404, detail="Artwork not found")
    if art["artist_id"] != current_user["id"]:
        cur.close()
        raise HTTPException(status_code=403, detail="Not your artwork")

    cur.execute("DELETE FROM artworks WHERE id = %s", (artwork_id,))
    db.commit()
    cur.close()
    return {"message": "Artwork deleted"}


# ----------------------------------------------------------------------------
# Purchase routes — Razorpay checkout flow
#
# Flow:
#   1. Frontend calls POST /artworks/{id}/checkout  -> we create a Razorpay
#      order and a 'pending' row in `purchases`, return the order_id to the
#      frontend.
#   2. Frontend opens Razorpay's checkout popup using that order_id.
#   3. On success, Razorpay gives the frontend a payment_id + signature.
#   4. Frontend sends those to POST /payments/verify. We verify the signature
#      OURSELVES on the server using our secret key — we never trust the
#      frontend's word that a payment succeeded — and only then mark the
#      purchase 'paid'.
# ----------------------------------------------------------------------------

@app.post("/artworks/{artwork_id}/checkout", status_code=201)
def checkout_artwork(artwork_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM artworks WHERE id = %s", (artwork_id,))
    art = cur.fetchone()
    if not art:
        cur.close()
        raise HTTPException(status_code=404, detail="Artwork not found")
    if art["artist_id"] == current_user["id"]:
        cur.close()
        raise HTTPException(status_code=400, detail="You can't buy your own artwork")
    if art["stock"] <= 0:
        cur.close()
        raise HTTPException(status_code=400, detail="This artwork is sold out")

    # Razorpay wants the amount in the smallest currency unit — paise, not rupees.
    amount_paise = int(float(art["price"]) * 100)

    razorpay_order = razorpay_client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"artwork_{artwork_id}_user_{current_user['id']}_{uuid.uuid4().hex[:8]}",
        "notes": {
            "artwork_id": str(artwork_id),
            "buyer_id": str(current_user["id"]),
        },
    })

    cur.execute(
        """INSERT INTO purchases (buyer_id, artwork_id, amount, razorpay_order_id, status)
           VALUES (%s, %s, %s, %s, 'pending')""",
        (current_user["id"], artwork_id, art["price"], razorpay_order["id"]),
    )
    db.commit()
    cur.close()

    return {
        "order_id": razorpay_order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID,
        "artwork_title": art["title"],
        "buyer_name": current_user["name"],
        "buyer_email": current_user["email"],
    }


@app.post("/payments/verify")
def verify_payment(payload: VerifyPayment, current_user=Depends(get_current_user), db=Depends(get_db)):
    # --- Step 1: verify the signature ---
    body = f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}"
    expected_signature = hmac.new(
        key=RAZORPAY_KEY_SECRET.encode(),
        msg=body.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, payload.razorpay_signature):
        cur = db.cursor()
        cur.execute(
            "UPDATE purchases SET status = 'failed' WHERE razorpay_order_id = %s",
            (payload.razorpay_order_id,),
        )
        db.commit()
        cur.close()
        raise HTTPException(status_code=400, detail="Payment verification failed — signature mismatch")

    # --- Step 2: confirm order belongs to this user ---
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM purchases WHERE razorpay_order_id = %s",
        (payload.razorpay_order_id,),
    )
    purchase = cur.fetchone()
    if not purchase:
        cur.close()
        raise HTTPException(status_code=404, detail="No matching order found")
    if purchase["buyer_id"] != current_user["id"]:
        cur.close()
        raise HTTPException(status_code=403, detail="This order does not belong to you")

    # --- Step 3: atomically decrement stock — only if stock > 0 ---
    # UPDATE ... WHERE stock > 0 means the decrement and the check happen in
    # a single SQL statement, so two simultaneous payments can't both pass a
    # Python-level stock > 0 check and both decrement past zero. This is the
    # correct way to handle race conditions on inventory without explicit locks.
    cur2 = db.cursor()
    cur2.execute(
        "UPDATE artworks SET stock = stock - 1 WHERE id = %s AND stock > 0",
        (purchase["artwork_id"],),
    )
    if cur2.rowcount == 0:
        # rowcount == 0 means the WHERE stock > 0 condition failed —
        # someone else bought the last copy between checkout and verify.
        cur2.close()
        cur.close()
        db.rollback()
        raise HTTPException(status_code=400, detail="Sorry, this artwork just sold out")

    # --- Step 4: mark purchase as paid ---
    cur.execute(
        """UPDATE purchases
           SET status = 'paid', razorpay_payment_id = %s
           WHERE razorpay_order_id = %s""",
        (payload.razorpay_payment_id, payload.razorpay_order_id),
    )
    db.commit()
    cur2.close()
    cur.close()

    return {"message": "Payment verified successfully", "status": "paid"}


@app.get("/my-purchases")
def my_purchases(current_user=Depends(get_current_user), db=Depends(get_db)):
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT a.id, a.title, a.image_path, p.amount AS price, p.purchased_at
        FROM purchases p
        JOIN artworks a ON p.artwork_id = a.id
        WHERE p.buyer_id = %s AND p.status = 'paid'
        ORDER BY p.purchased_at DESC
    """, (current_user["id"],))
    rows = cur.fetchall()
    cur.close()
    for r in rows:
        r["purchased_at"] = str(r["purchased_at"])
    return rows


@app.get("/my-artworks")
def my_artworks(current_user=Depends(get_current_user), db=Depends(get_db)):
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, title, image_path, price, category, created_at
        FROM artworks WHERE artist_id = %s ORDER BY created_at DESC
    """, (current_user["id"],))
    rows = cur.fetchall()
    cur.close()
    for r in rows:
        r["created_at"] = str(r["created_at"])
    return rows


@app.get("/")
def root():
    return {"message": "Digital Art Marketplace API is running"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)