import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app import models  # noqa: F401  (registers the tables with Base.metadata)
from app import dev_mode
from app.migrate import run_migrations
from app.seed import seed
from app.routes import auth, users, events, passes, admin, committees, colleges, fests, entry_passes, fest_events, gate, student, media, event_questions, announcements, short_links, transfers, event_import, invites, dev_switch, fest_teams, fest_tasks, fest_meetings, fest_schedule, contingents, fest_sponsors, dashboard, competition, cl_meets

IS_PRODUCTION = os.getenv("APP_ENV", "development") == "production"

# The interactive docs list every endpoint, so they are switched off in production
app = FastAPI(
    title="HiveOut API",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# Comma-separated list of frontend origins allowed to call the API (set ALLOWED_ORIGINS in production).
DEFAULT_DEV_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", DEFAULT_DEV_ORIGINS).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # using Bearer tokens (no cookies), so credentials not needed
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith(("/api/admin", "/api/auth", "/api/users")):
        response.headers["Cache-Control"] = "no-store"  # account and admin data is never kept by a cache
    return response

app.include_router(auth.router,          prefix="/api/auth",        tags=["Auth"])
app.include_router(users.router,         prefix="/api/users",       tags=["Users"])
app.include_router(events.router,        prefix="/api/events",      tags=["Events"])
app.include_router(passes.router,        prefix="/api/passes",      tags=["Passes"])
app.include_router(admin.router,         prefix="/api/admin",       tags=["Admin"])
app.include_router(committees.router,    prefix="/api/events",      tags=["Committees"])
app.include_router(colleges.router,      prefix="/api/colleges",    tags=["Colleges"])
app.include_router(fests.router,         prefix="/api/fests",       tags=["Fests"])
app.include_router(entry_passes.router,  prefix="/api/fests",       tags=["FestPasses"])
app.include_router(student.router,        prefix="/api/users/me/student", tags=["Student verification"])
app.include_router(media.router,          prefix="/api/media",       tags=["Media"])
app.include_router(event_questions.router, prefix="/api/events",     tags=["Event questions"])
app.include_router(announcements.router,  prefix="/api/fests",       tags=["Announcements"])
app.include_router(announcements.notifications_router, prefix="/api/users/me", tags=["Announcements"])
app.include_router(transfers.router,     prefix="/api",             tags=["Fest transfers"])
app.include_router(invites.router,       prefix="/api",             tags=["Team invitations"])
app.include_router(invites.notices_router, prefix="/api/users/me",    tags=["Account notices"])
app.include_router(event_import.router,  prefix="/api/fests",       tags=["Event import"])
app.include_router(fest_teams.router,   prefix="/api/fests",       tags=["Committee structure"])
app.include_router(fest_tasks.router,   prefix="/api/fests",       tags=["Committee tasks"])
app.include_router(fest_meetings.router, prefix="/api/fests",     tags=["Committee meetings"])
app.include_router(fest_schedule.router, prefix="/api/fests",     tags=["Fest schedule"])
app.include_router(contingents.router,   prefix="/api/fests",       tags=["Contingents"])
app.include_router(fest_sponsors.router, prefix="/api/fests",       tags=["Sponsors"])
app.include_router(competition.router,   prefix="/api/fests",       tags=["Competition"])
app.include_router(cl_meets.router,      prefix="/api/fests",       tags=["CL meets"])
app.include_router(dashboard.router,     prefix="/api/dashboard",   tags=["Dashboard"])
app.include_router(short_links.router,   prefix="/api/short-links", tags=["Short links"])
app.include_router(gate.router,           prefix="/api/fests",       tags=["Gate"])
app.include_router(fest_events.router,   prefix="/api/fest-events", tags=["FestEventRegistrations"])
if dev_mode.enabled():  # local development only: needs APP_ENV != production and DEV_ROLE_SWITCHER=1
    app.include_router(dev_switch.router, prefix="/api/dev",        tags=["Dev"])

@app.on_event("startup")
def on_startup():
    run_migrations()
    seed()

@app.get("/")
def root():
    return {"message": "HiveOut API is running"}