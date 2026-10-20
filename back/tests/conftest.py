import os

# Must be set before app.auth.jwt is imported (it refuses to load without a strong key).
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-used-anywhere-else-0123456789")
