# EventX

College-fest and city-event platform: discover fests, get a free entry pass, register for events, and manage events as an organiser or admin.

```
eventx/
├── back/                 FastAPI API
│   ├── app/
│   │   ├── main.py       app, CORS, routers, startup seed
│   │   ├── seed.py       first-run data (colleges, sample fests, optional admin/organiser accounts)
│   │   ├── models.py     SQLAlchemy tables
│   │   ├── schemas.py    request/response models and validation
│   │   ├── permissions.py  who can see or manage events and fests
│   │   ├── database.py   engine and session
│   │   ├── auth/         JWT tokens and login dependencies
│   │   └── routes/       one module per area (auth, events, fests, passes, ...)
│   ├── tests/            pytest suite (in-memory SQLite)
│   ├── .env.example      every setting the API reads
│   └── requirements*.txt
├── web/                  New HiveOut site: Next.js + Tailwind (student side)
│   └── src/
│       ├── app/          pages (home, fests, events, fest and event detail, sign in, My passes, profile)
│       ├── components/   glass UI pieces, cards, registration and pass panels
│       └── lib/          API client, auth, formatting, share-card images
├── front/                Old React + Vite app (still serves the committee dashboard until it moves to web/)
│   └── src/
│       ├── pages/        route-level screens (Fests/ holds the fest screens)
│       ├── components/   shared UI
│       ├── context/      auth state
│       ├── services/     API client
│       └── lib/          helpers (error messages, static data)
└── render.yaml           Render Blueprint for both services
```

## Run locally

Backend (Python 3.9+):

```bash
cd back
python3 -m venv venv
./venv/bin/pip install -r requirements-dev.txt
cp .env.example .env      # then set SECRET_KEY (see the comment in the file)
./venv/bin/uvicorn app.main:app --reload --port 8000
```

Website (Node 20+):

```bash
cd web
npm install
cp .env.example .env.local
npm run dev               # http://localhost:3000
```

Committee dashboard (old app, until it is rebuilt in `web/`): `cd front && npm install && npm run dev` (http://localhost:5173).

Tests: `cd back && ./venv/bin/python -m pytest`

## Settings that matter

- `SECRET_KEY` is required (32+ characters). The API refuses to start without it.
- `ALLOWED_ORIGINS` lists the frontend URLs allowed to call the API.
- No default accounts exist. Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` (12+ characters) to create the first admin on startup.
- `ORGANIZER_<FEST>_EMAIL` / `_PASSWORD` optionally create an owner for each seeded fest.

## Known limitations

- Paid events do not take payment: registering for one marks it as paid. Connect a payment provider before charging anyone.
- There is no gate-scanning screen yet. The API (`POST /api/fests/{slug}/gate-scan/{pass_id}`) exists and the pass QR code is shown in My Passes.
- SQLite on Render needs a paid disk; use Postgres for real data.
