"""First-run seed data: lookup lists, colleges, sample fests/events, and optional accounts from the environment."""

import os
from datetime import datetime, timedelta
from app.database import SessionLocal
from app import models

MIN_SEED_PASSWORD_LENGTH = 12

def _seed_credentials(email_var: str, password_var: str):
    """Read an account's email/password from the environment. Returns None unless both are set and the password is strong enough."""
    email = os.getenv(email_var, "").strip()
    password = os.getenv(password_var, "")
    if not email or not password:
        return None
    if len(password) < MIN_SEED_PASSWORD_LENGTH:
        print(f"[seed] {password_var} is shorter than {MIN_SEED_PASSWORD_LENGTH} characters; skipping that account")
        return None
    return email, password

def seed():
    db = SessionLocal()
    try:
        if db.query(models.Interest).count() == 0:
            interests = ["Music", "Technology", "Festival", "Art", "Business", "Design", "Sports", "Food", "Comedy", "Education"]
            for name in interests:
                db.add(models.Interest(name=name))
            db.commit()

        if db.query(models.College).count() == 0:
            seed_colleges = [
                {"name": "IIT Bombay",     "area": "Powai, Mumbai",     "emoji": "🏛️", "website": "https://www.iitb.ac.in"},
                {"name": "St. Xavier's",   "area": "Fort, Mumbai",      "emoji": "⛪"},
                {"name": "NMIMS",          "area": "Vile Parle, Mumbai", "emoji": "🎓"},
                {"name": "VJTI",           "area": "Matunga, Mumbai",   "emoji": "⚙️", "website": "https://vjti.ac.in"},
                {"name": "ICT Mumbai",     "area": "Matunga, Mumbai",   "emoji": "🔬"},
                {"name": "SP Jain",        "area": "Matunga, Mumbai",   "emoji": "💼"},
                {"name": "KJ Somaiya",     "area": "Vidyavihar, Mumbai","emoji": "📚"},
                {"name": "Thadomal Shahani","area": "Bandra, Mumbai",   "emoji": "🏢"},
            ]
            for c in seed_colleges:
                db.add(models.College(**c))
            db.commit()

        if db.query(models.User).filter(models.User.role == "admin").count() == 0:
            creds = _seed_credentials("ADMIN_EMAIL", "ADMIN_PASSWORD")
            if creds:
                from passlib.context import CryptContext
                pwd = CryptContext(
                    schemes=["bcrypt"],
                    deprecated="auto",
                    bcrypt__truncate_error=False,  # truncate >72 bytes to avoid backend ValueError
                )
                admin_email, admin_password = creds
                db.add(models.User(
                    name="EventX Admin",
                    email=admin_email,
                    hashed_password=pwd.hash(admin_password[:72]),
                    role=models.RoleEnum.admin,
                    auth_provider=models.AuthProviderEnum.email,
                    interests_set=True,
                ))
                db.commit()
            else:
                print("[seed] No admin exists and ADMIN_EMAIL / ADMIN_PASSWORD are not set; no admin account created")

        # Seed fests + their organizer accounts + owner FestMember rows
        # Everything happens in one transaction so the DB is never in a half-seeded state.
        if db.query(models.Fest).count() == 0:
            from passlib.context import CryptContext
            pwd = CryptContext(
                schemes=["bcrypt"],
                deprecated="auto",
                bcrypt__truncate_error=False,
            )

            iitb   = db.query(models.College).filter(models.College.name == "IIT Bombay").first()
            xavier = db.query(models.College).filter(models.College.name == "St. Xavier's").first()
            nmims  = db.query(models.College).filter(models.College.name == "NMIMS").first()

            # ── Seed organizer accounts (one per flagship fest) ───────────────
            # Credentials come from the environment (ORGANIZER_<SLUG>_EMAIL / ORGANIZER_<SLUG>_PASSWORD,
            # e.g. ORGANIZER_MOOD_INDIGO_EMAIL). A fest without configured credentials is created with no
            # owner; an admin can assign one afterwards.
            seed_organizers = [
                {"slug": "mood-indigo",  "name": "Mood Indigo Team"},
                {"slug": "malhar",       "name": "Malhar Team"},
                {"slug": "kaleidoscope", "name": "Kaleidoscope Team"},
            ]
            organizer_users = []
            for o in seed_organizers:
                prefix = "ORGANIZER_" + o["slug"].upper().replace("-", "_")
                creds = _seed_credentials(prefix + "_EMAIL", prefix + "_PASSWORD")
                if not creds:
                    organizer_users.append(None)
                    continue
                email, password = creds
                # Skip if account already exists (idempotent re-runs)
                existing = db.query(models.User).filter(models.User.email == email).first()
                if existing:
                    organizer_users.append(existing)
                else:
                    user = models.User(
                        name=o["name"],
                        email=email,
                        hashed_password=pwd.hash(password[:72]),
                        role=models.RoleEnum.organizer,
                        auth_provider=models.AuthProviderEnum.email,
                        interests_set=True,
                    )
                    db.add(user)
                    organizer_users.append(user)

            # flush so organizer PKs are populated before FestMember FK refs
            db.flush()

            # ── Seed fests ────────────────────────────────────────────────────
            seed_fests_meta = [
                {
                    "slug": "mood-indigo",
                    "name": "Mood Indigo",
                    "tagline": "Asia's Largest College Cultural Festival",
                    "banner_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1600",
                    "logo_url": "https://images.unsplash.com/photo-1614680376408-81e91ffe3db7?w=400",
                    "college_id": iitb.id if iitb else None,
                    "status": models.FestStatusEnum.live,
                    "owner_idx": 0,   # index into organizer_users
                },
                {
                    "slug": "malhar",
                    "name": "Malhar",
                    "tagline": "Mumbai's Most Iconic Street Festival",
                    "banner_url": "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=1600",
                    "logo_url": "https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?w=400",
                    "college_id": xavier.id if xavier else None,
                    "status": models.FestStatusEnum.live,
                    "owner_idx": 1,
                },
                {
                    "slug": "kaleidoscope",
                    "name": "Kaleidoscope",
                    "tagline": "Where Creativity Meets Innovation",
                    "banner_url": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=1600",
                    "logo_url": "https://images.unsplash.com/photo-1504680177321-2e6a879aac86?w=400",
                    "college_id": nmims.id if nmims else None,
                    "status": models.FestStatusEnum.live,
                    "owner_idx": 2,
                },
            ]

            for meta in seed_fests_meta:
                owner_idx = meta.pop("owner_idx")
                fest = models.Fest(**meta)
                db.add(fest)
                db.flush()  # populate fest.id before FK reference

                owner = organizer_users[owner_idx]
                if owner is not None:
                    db.add(models.FestMember(
                        fest_id=fest.id,
                        user_id=owner.id,
                        role=models.FestMemberRoleEnum.owner,
                    ))

            db.commit()  # single commit — fest + organizer + member rows are atomic

        # Seed sample events (tech / finance / design)
        if db.query(models.Event).count() == 0:
            base_date = datetime.utcnow() + timedelta(days=3)

            # Ensure fests exist first (or fetch them if already seeded)
            def get_fest_id(slug):
                f = db.query(models.Fest).filter(models.Fest.slug == slug).first()
                return f.id if f else None

            mood_id   = get_fest_id("mood-indigo")
            malhar_id = get_fest_id("malhar")
            kaleido_id = get_fest_id("kaleidoscope")

            samples = [
                # ── Fest events (event_type="fest") ──────────────────────────────
                {
                    "event_type": models.EventTypeEnum.fest,
                    "title": "Future of AI Summit",
                    "description": "Keynotes and live demos on GenAI, agents, and edge inference.",
                    "location": "Online / Virtual Stage",
                    "category": "Technology",
                    "date": base_date,
                    "time": "10:00",
                    "price": 0,
                    "is_free": True,
                    "status": models.StatusEnum.approved,
                    "image_url": "https://images.unsplash.com/photo-1518770660439-4636190af475",
                    "fest_id": mood_id,
                    "organizer_id": None,
                },
                {
                    "event_type": models.EventTypeEnum.fest,
                    "title": "FinTech Infra Day",
                    "description": "Payments, compliance, and API-first banking deep dives.",
                    "location": "NYC · Hudson Yards",
                    "category": "Finance",
                    "date": base_date + timedelta(days=2),
                    "time": "14:00",
                    "price": 49,
                    "is_free": False,
                    "status": models.StatusEnum.approved,
                    "image_url": "https://images.unsplash.com/photo-1454165205744-3b78555e5572",
                    "fest_id": malhar_id,
                    "organizer_id": None,
                },
                {
                    "event_type": models.EventTypeEnum.fest,
                    "title": "Design Systems Lab",
                    "description": "Hands-on workshop building accessible, animated design systems.",
                    "location": "SF · SoMa",
                    "category": "Design",
                    "date": base_date + timedelta(days=5),
                    "time": "09:30",
                    "price": 0,
                    "is_free": True,
                    "status": models.StatusEnum.approved,
                    "image_url": "https://images.unsplash.com/photo-1521737604893-d14cc237f11d",
                    "fest_id": kaleido_id,
                    "organizer_id": None,
                },
                {
                    "event_type": models.EventTypeEnum.fest,
                    "title": "Web3 Builders Meetup",
                    "description": "L2 rollups, account abstraction, and onchain gaming demos.",
                    "location": "Bengaluru · Indiranagar",
                    "category": "Technology",
                    "date": base_date + timedelta(days=7),
                    "time": "18:30",
                    "price": 0,
                    "is_free": True,
                    "status": models.StatusEnum.approved,
                    "image_url": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4",
                    "fest_id": mood_id,
                    "organizer_id": None,
                },
                # ── City events (event_type="city") ──────────────────────────────
                {
                    "event_type": models.EventTypeEnum.city,
                    "title": "Mumbai Startup Pitch Night",
                    "description": "10 early-stage founders pitch live. Angels, VCs, and free beer.",
                    "location": "Mumbai · Lower Parel",
                    "category": "Business",
                    "date": base_date + timedelta(days=4),
                    "time": "19:00",
                    "price": 0,
                    "is_free": True,
                    "status": models.StatusEnum.approved,
                    "image_url": "https://images.unsplash.com/photo-1556761175-4b46a572b786",
                    "fest_id": None,
                    "organizer_id": None,  # no organizer user yet at seed time
                },
                {
                    "event_type": models.EventTypeEnum.city,
                    "title": "Indie Music Open Mic",
                    "description": "Monthly open mic for original music. Acoustic, indie, and experimental.",
                    "location": "Pune · Koregaon Park",
                    "category": "Music",
                    "date": base_date + timedelta(days=9),
                    "time": "20:00",
                    "price": 200,
                    "is_free": False,
                    "status": models.StatusEnum.approved,
                    "image_url": "https://images.unsplash.com/photo-1501612780327-45045538702b",
                    "fest_id": None,
                    "organizer_id": None,
                },
            ]
            for data in samples:
                db.add(models.Event(**data))
            db.commit()
    finally:
        db.close()
