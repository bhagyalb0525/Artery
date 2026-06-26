# Artery — Digital Art Marketplace

A full-stack web app where artists can upload digital artwork and buyers can browse, search, filter, and purchase pieces.

**Stack:** HTML/CSS/JS (frontend) · FastAPI (backend) · MySQL (database)

---

## Folder structure

```
artmarket/
├── .gitignore              # keeps .env, __pycache__, uploads out of git
├── backend/
│   ├── main.py            # FastAPI app — all routes, models, DB logic
│   ├── requirements.txt   # Python dependencies
│   ├── schema.sql         # MySQL schema (for reference / manual setup)
│   ├── .env               # YOUR real secrets — never committed
│   └── .env.example        # template — this one IS committed
├── frontend/
│   ├── index.html         # Page structure
│   ├── style.css          # Styling (responsive)
│   └── script.js          # Frontend logic (fetch calls to backend)
└── static/
    └── uploads/           # Uploaded artwork images get saved here
```

---

## 1. Set up MySQL

Make sure MySQL Server is installed and running. Then create the database:

```bash
mysql -u root -p < backend/schema.sql
```

(This just creates the `art_marketplace` database and tables. The FastAPI app will also auto-create the tables on startup if they don't exist, so this step is optional but good practice.)

---

## 2. Set up the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Copy the example env file and fill in your real values:

```bash
cp .env.example .env
```

Open `.env` and set your MySQL password and a random secret key:

```env
DB_PASSWORD=your_actual_mysql_password
SECRET_KEY=paste_a_long_random_string_here
```

Generate a strong `SECRET_KEY` with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

`.env` is git-ignored on purpose — it holds real secrets and should never be pushed to GitHub. `.env.example` is the template that *does* get committed, so anyone cloning the repo knows which variables to set.

Run the server:

```bash
python main.py
```

The API will start at **http://127.0.0.1:8000**
You can view interactive API docs at **http://127.0.0.1:8000/docs**

---

## 3. Run the frontend

The frontend is plain HTML/CSS/JS, so you just need to serve the `frontend/` folder. The simplest way:

```bash
cd frontend
python -m http.server 5500
```

Then open **http://127.0.0.1:5500** in your browser.

(You can also just double-click `index.html`, but serving it through a local server avoids some browser quirks with fetch requests.)

> If your frontend runs on a different port than 5500, add that origin to `ALLOWED_ORIGINS` in your `.env` file, or the backend will reject the request with a CORS error. Also make sure `API_BASE` at the top of `script.js` matches wherever your backend is actually running.

---

## Pushing this to GitHub

From the project root (`artmarket/`):

```bash
git init
git add .
git status   # double-check .env is NOT listed here — it should be ignored
git commit -m "Initial commit: digital art marketplace"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

The `git status` check matters — if `.env` shows up as a file about to be committed, **stop** and make sure `.gitignore` is sitting in the project root (same level as `backend/` and `frontend/`) before you commit.

If you ever accidentally commit `.env` before adding `.gitignore`, deleting the file afterward isn't enough — it stays in git history. In that case, change your `SECRET_KEY` and DB password right away, and ask if you need help scrubbing it from history.

---

## Deploying

Backend and frontend deploy separately.

- **Backend (FastAPI + MySQL)**: platforms like Render, Railway, or PythonAnywhere work well for students and have free tiers. You'll set `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `SECRET_KEY`, and `ALLOWED_ORIGINS` as environment variables in the platform's dashboard — not in a committed `.env`. Most platforms also offer a managed MySQL add-on, or you can use a free MySQL instance from Railway/PlanetScale.
- **Frontend (static HTML/CSS/JS)**: GitHub Pages, Netlify, or Vercel can serve `frontend/` directly. After deploying, update `API_BASE` at the top of `script.js` to your live backend URL instead of `127.0.0.1:8000`.
- Update `ALLOWED_ORIGINS` in your backend's environment variables to include your deployed frontend's URL — otherwise the browser blocks the requests with a CORS error.

---

## How it works (quick overview for explaining in interviews)

- **Auth**: Signup/login hashes passwords with bcrypt and issues a JWT. The token is stored in `localStorage` and sent as a `Bearer` token on every authenticated request.
- **Browsing**: `GET /artworks` is public — no login needed. Supports `?category=` and `?search=` query params for filtering.
- **Uploading**: `POST /artworks` is authenticated, accepts `multipart/form-data` (title, description, price, category, image file). The image is saved to `static/uploads/` with a UUID filename, and the path is stored in MySQL.
- **Buying**: `POST /artworks/{id}/buy` records a purchase row linking buyer and artwork. (No real payment gateway is wired up — this just simulates the transaction, which is normal for a college/resume project unless you want to add Razorpay/Stripe later.)
- **Database design**: Three tables — `users`, `artworks`, `purchases` — with foreign keys enforcing that artworks belong to a user and purchases reference both a buyer and an artwork.

## Ideas for extending it later (good talking points for interviews)

- Pagination for the gallery instead of loading everything at once
- A real payment gateway integration (Razorpay test mode is easy to demo)
- Image optimization/thumbnails on upload (Pillow)
- Ratings/reviews on artworks
- Artist profile pages
- Dockerizing the backend + MySQL with `docker-compose`