import firebase_admin
from firebase_admin import credentials
from firebase_admin import auth
from firebase_admin import db
import os

def create_firebase_users():
    """Creates Firebase Authentication users and sets their objectives in Realtime Database."""

    # --- Firebase Initialization - Manual Credential Loading - INSECURE, FOR LOCAL TESTING ONLY ---
    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": "YOUR_PROJECT_ID",                 # Replace with your Project ID
        "private_key_id": "YOUR_PRIVATE_KEY_ID",           # Replace with your private_key_id from serviceAccountKey.json
        "private_key": "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_CONTENT_HERE\n-----END PRIVATE KEY-----\n", # Replace with your private_key content (multi-line string)
        "client_email": "YOUR_CLIENT_EMAIL",             # Replace with your client_email
        "client_id": "YOUR_CLIENT_ID",                 # Replace with your client_id
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/YOUR_CLIENT_X509_CERT_URL", # Replace with your client_x509_cert_url
        "universe_domain": "googleapis.com"
    })

    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://ams-hackathon-2025-default-rtdb.firebaseio.com'
    })

    users_data = [
        {"username": "team1", "password": "password1", "objective": "NUM3R1C_FUSION CHALLENGE"},
        {"username": "team2", "password": "password2", "objective": "DATA_INTEGRATION TASK"},
        {"username": "team3", "password": "password3", "objective": "ALGORITHM_DESIGN PROBLEM"},
        # Add more users/teams here if needed
    ]

    users_ref = db.reference('/usersData')

    for user_info in users_data:
        try:
            # Create user in Firebase Authentication
            user = auth.create_user(
                email=f"{user_info['username']}@hackathon.ams",  # Using username as email prefix
                password=user_info['password']
            )
            print(f"Successfully created user: {user_info['username']} with UID: {user.uid}")

            # Store objective in Realtime Database, linked to the user's UID
            users_ref.child(user.uid).set({
                "objective": user_info["objective"]
            })
            print(f"  Objective set for user: {user_info['username']}")

        except auth.EmailAlreadyExistsError:
            print(f"User with email {user_info['username']}@hackathon.ams already exists. Skipping creation.")
        except Exception as e:
            print(f"Error creating user {user_info['username']}: {e}")

    firebase_admin.delete_app(firebase_admin.get_app())

    print("\n--- User creation script finished ---")


if __name__ == "__main__":
    create_firebase_users()