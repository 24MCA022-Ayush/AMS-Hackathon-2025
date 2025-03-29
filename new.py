import secrets
import os

# Generate a random hex string of 32 bytes (256 bits), which is a good length for a secret key
secret_key = secrets.token_hex(32)

print(f"Generated Secret Key: {secret_key}")

# --- How to use it in your Flask app ---
# In your app.py file:
# app.secret_key = os.environ.get('FLASK_SECRET_KEY', secret_key) # Use the generated key as default for development

# --- For production, set FLASK_SECRET_KEY environment variable ---
# In your Render, Heroku, or other deployment environment, set an environment variable named:
# FLASK_SECRET_KEY
# and paste the generated `secret_key` value as its value.