import os

# Must be set before app.auth.jwt is imported (it refuses to load without a strong key).
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-used-anywhere-else-0123456789")

# Password hashing is deliberately slow. Tests make hundreds of accounts, so they use the cheapest cost (production always uses 12).
os.environ.setdefault("BCRYPT_ROUNDS", "4")
