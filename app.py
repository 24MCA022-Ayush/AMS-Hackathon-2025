from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, session # Import redirect and session
import os
import secrets
import subprocess
import tempfile
import uuid
import json
import time
import re
from werkzeug.utils import secure_filename
import shutil
from flask_session import Session # Import Flask-Session
from functools import wraps # for login_required decorator

# --- Firebase Admin SDK ---
import firebase_admin
from firebase_admin import credentials
from firebase_admin import auth # Import auth
from firebase_admin import db

# --- SendGrid ---  <--- ADD THESE LINES
import sendgrid
from sendgrid.helpers.mail import Mail

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['TEST_CASES_FOLDER'] = 'test_cases'
app.config['CONFIG_FOLDER'] = 'config'

# Configure session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem" # Use filesystem for sessions
Session(app) # Initialize Flask-Session

app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key') # Good practice to set a secret key


# Load Java paths if they exist
java_path = 'java'  # Default fallback
javac_path = 'javac'  # Default fallback

java_config_file = os.path.join(app.config['CONFIG_FOLDER'], 'java_paths.json')
if os.path.exists(java_config_file):
    try:
        with open(java_config_file, 'r') as f:
            java_config = json.load(f)
            if java_config.get('java_path'):
                java_path = java_config['java_path']
            if java_config.get('javac_path'):
                javac_path = java_config['javac_path']
        print(f"Using Java paths: java={java_path}, javac={javac_path}")
    except Exception as e:
        print(f"Error loading Java paths: {e}")

# If paths are empty, try to find them from alternative paths
if not java_path or not javac_path:
    alt_java_paths_file = os.path.join(app.config['CONFIG_FOLDER'], 'alt_java_paths.txt')
    alt_javac_paths_file = os.path.join(app.config['CONFIG_FOLDER'], 'alt_javac_paths.txt')

    if os.path.exists(alt_java_paths_file):
        try:
            with open(alt_java_paths_file, 'r') as f:
                paths = f.readlines()
                if paths:
                    java_path = paths[0].strip()
                    print(f"Using alternative Java path: {java_path}")
        except Exception as e:
            print(f"Error loading alternative Java paths: {e}")

    if os.path.exists(alt_javac_paths_file):
        try:
            with open(alt_javac_paths_file, 'r') as f:
                paths = f.readlines()
                if paths:
                    javac_path = paths[0].strip()
                    print(f"Using alternative JavaC path: {javac_path}")
        except Exception as e:
            print(f"Error loading alternative JavaC paths: {e}")

app.config['SUPPORTED_LANGUAGES'] = {
    'cpp': {
        'file_ext': '.cpp',
        'compile_cmd': ['g++', '-std=c++17', '{source_file}', '-o', '{exe_file}'],
        'run_cmd': ['{exe_file}'],
        'timeout': 5
    },
    'c': {
        'file_ext': '.c',
        'compile_cmd': ['gcc', '{source_file}', '-o', '{exe_file}'],
        'run_cmd': ['{exe_file}'],
        'timeout': 5
    },
    'java': {
        'file_ext': '.java',
        'compile_cmd': [javac_path, '{source_file}'],
        'run_cmd': [java_path, '-classpath', '{dir}', '{classname}'],
        'timeout': 8
    },
    'python': {
        'file_ext': '.py',
        'compile_cmd': None,  # Python doesn't need compilation
        'run_cmd': ['python3', '{source_file}'],
        'timeout': 6
    }
}

# Ensure upload and test case directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEST_CASES_FOLDER'], exist_ok=True)

# Create default test cases if they don't exist
def create_default_test_cases():
    test_cases = [
        {"id": "1", "input": "5 7\n", "expected_output": "12\n"},
        {"id": "2", "input": "10 20\n", "expected_output": "30\n"},
        {"id": "3", "input": "0 0\n", "expected_output": "0\n"},
        {"id": "4", "input": "-5 10\n", "expected_output": "5\n"},
        {"id": "5", "input": "100 -30\n", "expected_output": "70\n"}
    ]

    test_cases_file = os.path.join(app.config['TEST_CASES_FOLDER'], 'test_cases.json')
    if not os.path.exists(test_cases_file):
        with open(test_cases_file, 'w') as f:
            json.dump(test_cases, f, indent=2)

create_default_test_cases()

# --- Firebase Initialization - Manual Credential Loading (NOT RECOMMENDED for production) ---
credentials_json_string = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

if credentials_json_string:
    try:
        service_account_info = json.loads(credentials_json_string)
        cred = credentials.Certificate(service_account_info) # Initialize from dictionary
    except json.JSONDecodeError as e:
        print(f"Error decoding GOOGLE_APPLICATION_CREDENTIALS JSON: {e}")
        # Handle error appropriately - maybe exit or use default credentials?
        cred = credentials.ApplicationDefault() # Fallback to Application Default in case of error
    except Exception as e:
        print(f"Error initializing Firebase from GOOGLE_APPLICATION_CREDENTIALS: {e}")
        cred = credentials.ApplicationDefault() # Fallback
else:
    print("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
    cred = credentials.ApplicationDefault() # Fallback

firebase_admin.initialize_app(cred, {
    'databaseURL': os.environ.get('FIREBASE_DATABASE_URL') # Keep using environment variable for Database URL
})

# Reference to the node where your challenge data is stored in Firebase
challenge_data_ref = db.reference('/challengeData') # Assuming your data is under a 'challengeData' node

# --- Login Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("team_name") is None:
            return redirect("/login") # Redirect to login if not logged in
        return f(*args, **kwargs)
    return decorated_function

# --- Session Management Routes ---
@app.route('/api/login_session', methods=['POST'])
def login_session():
    data = request.get_json()
    team_name = data.get('teamName')
    if team_name:
        session["team_name"] = team_name # Store team name in session
        return jsonify({"status": "success", "message": "Session initialized"}), 200
    return jsonify({"status": "error", "message": "Team name missing"}), 400

@app.route('/api/logout_session', methods=['POST'])
def logout_session():
    session.pop("team_name", None) # Clear session data
    return jsonify({"status": "success", "message": "Logged out"}), 200

# Reference to the node where your teams data will be stored in Firebase
teams_data_ref = db.reference('/Teams_Data')

@app.route('/register')
def registration_page():
    return render_template('registration.html') # Serve registration page


@app.route('/api/register_team', methods=['POST'])
def register_team():
    data = request.form # Use request.form to get form data

    team_name = data.get('team-name')
    num_members = data.get('num-members')
    lead_email = data.get('lead-email')
    lead_phone = data.get('lead-phone')
    transaction_id = data.get('transaction-id')
    payment_amount = data.get('payment-amount')

    team_members = {}
    team_member_1_email = None # Capture Team Member 1's email <--- ADD THIS LINE
    for i in range(1, int(num_members) + 1): # Assuming num_members is correctly validated on frontend
        member_data = {
            "Name": data.get(f'member-name-{i}'),
            "Email": data.get(f'member-email-{i}'),
            "Phone_No": data.get(f'member-phone-{i}'),
            "Course": data.get(f'member-course-{i}'),
            "Roll_No": data.get(f'member-enrollment-{i}')
        }
        team_members[f'Team_Member_{i}'] = member_data
        if i == 1: # Get email of Team Member 1 <--- ADD THIS BLOCK
            team_member_1_email = member_data["Email"]

    payment_info = {
        "Trans_Id": transaction_id,
        "Amount": payment_amount
    }

    try:
        # --- Firebase Authentication ---
        # Sanitize team_name to remove spaces for email address  <--- ADDED CODE
        sanitized_team_name = team_name.replace(" ", "_") # Replace spaces with underscores
        email = f"{sanitized_team_name}@hackathon.ams"
        password = team_name # As per your request - consider stronger passwords in production

        try:
            user = auth.create_user(
                email=email,
                password=password,
                display_name=team_name # Optional - set display name as team name
            )
            firebase_uid = user.uid
            print(f"Successfully created new user: {firebase_uid}")
        except auth.EmailAlreadyExistsError:
            return jsonify({"status": "error", "message": "Team name already taken. Please choose a different team name."}), 400
        except Exception as auth_error:
            print(f"Firebase Authentication Error: {auth_error}")
            return jsonify({"status": "error", "message": f"Authentication failed: {str(auth_error)}"}), 500

        # Generate a 12-digit alphanumeric secret key  <--- START OF ADDED CODE BLOCK
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        secret_key = ''.join(secrets.choice(alphabet) for i in range(12))

        print(f"Generated Secret Key for Team '{team_name}': {secret_key}") # Log the generated key for debugging (remove in production)

        # --- Firebase Realtime Database ---
        team_data_payload = {
            "Team_Name": team_name,
            "Secret_Key": secret_key, # Store the generated secret key - consider security implications
            "Domain": None, # Set default values as per your example
            "Title": None,
            "Domain_Process": False,
            "Payment_Info": payment_info,
            **team_members # Merge team members dictionary into the payload
        }

        teams_data_ref.child(firebase_uid).set(team_data_payload) # Use Firebase UID as key

         # --- Send Registration Confirmation Email ---  <--- START OF ADDED CODE BLOCK
        if team_member_1_email:
            try:
                sg = sendgrid.SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY')) # Initialize SendGrid client
                from_email = os.environ.get('SENDGRID_FROM_EMAIL')
                to_email = team_member_1_email
                subject = "CodeBlocs Hackathon 2025 - Registration Successful!"
                plain_text_content = f"Congratulations Team {team_name}!\n\n" \
                                     f"Your registration for CodeBlocs Hackathon 2025 is successful.\n\n" \
                                     f"Your Secret Key is: {secret_key}\n\n" \
                                     f"Please keep this key safe as it will be needed for future access.\n\n" \
                                     f"We look forward to seeing you at the hackathon!\n\n" \
                                     f"Best regards,\n" \
                                     f"The CodeBlocs Hackathon Team"
                html_content = f"<p>Congratulations Team {team_name}!</p>" \
                               f"<p>Your registration for CodeBlocs Hackathon 2025 is successful.</p>" \
                               f"<p><b>Your Secret Key is: {secret_key}</b></p>" \
                               f"<p>Please keep this key safe as it will be needed for future access.</p>" \
                               f"<p>We look forward to seeing you at the hackathon!</p>" \
                               f"<p>Best regards,<br>The CodeBlocs Hackathon Team</p>"

                message = Mail(from_email=from_email, to_emails=to_email, subject=subject, plain_text_content=plain_text_content, html_content=html_content)

                response = sg.send(message)
                print(f"Email sent to {team_member_1_email}, status code: {response.status_code}") # Log email sending status
                if response.status_code >= 400: # Log error if email sending fails
                    print(f"Email sending error: {response.body}")

            except Exception as e:
                print(f"SendGrid Email Sending Error: {e}") # Log any SendGrid related errors
                # Consider whether to return an error to the user or just log and continue.
                # For registration success, often logging and continuing is acceptable if email is non-critical.


        return jsonify({"status": "success", "message": "Team registered successfully! Please check Team Member 1's email for confirmation."}), 200

    except Exception as db_error:
        print(f"Firebase Database Error: {db_error}")
        return jsonify({"status": "error", "message": f"Database error: {str(db_error)}"}), 500


@app.route('/')
def home_page():
    return render_template('home.html') # Serve home page at root

@app.route('/login')
def login_page():
    if session.get("team_name"): # If user is already logged in
        return redirect("/hackathon") # Redirect to hackathon page
    return render_template('login.html') # Serve login page at /login if not logged in

@app.route('/hackathon')
@login_required # Protect hackathon page
def hackathon_page():
    team_name = session.get("team_name") # Get team name from session
    try:
        # Fetch challenge data from Firebase
        challenge_data = challenge_data_ref.get()
        if challenge_data:
            return render_template('hackathon.html', challenge_data=challenge_data, team_name=team_name) # Serve hackathon page at /hackathon and pass team_name
        else:
            return "Error: Challenge data not found in Firebase.", 500 # Handle error if data is not found
    except Exception as e: # Catch potential Firebase errors
        return f"Error fetching challenge data from Firebase: {e}", 500 # Handle Firebase connection errors


@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

def get_test_cases():
    test_cases_file = os.path.join(app.config['TEST_CASES_FOLDER'], 'test_cases.json')
    with open(test_cases_file, 'r') as f:
        return json.load(f)

@app.route('/api/submit', methods=['POST']) # No login required for submission in this version, could be added
def submit_code():
    # Get the submitted code
    if 'code' not in request.files:
        return jsonify({"error": "No code file provided"})

    code_file = request.files['code']
    if code_file.filename == '':
        return jsonify({"error": "No file selected"})

    # Create a unique ID for this submission
    submission_id = str(uuid.uuid4())

    # Create a temporary directory for this submission
    temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], submission_id)
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # Save the uploaded file with a secure filename
        filename = secure_filename(code_file.filename)
        file_path = os.path.join(temp_dir, filename)
        code_file.save(file_path)

        # Detect the programming language from file extension
        file_ext = os.path.splitext(filename)[1].lower()
        language = None

        for lang, config in app.config['SUPPORTED_LANGUAGES'].items():
            if file_ext == config['file_ext']:
                language = lang
                break

        if language is None:
            return jsonify({
                "status": "error",
                "phase": "validation",
                "message": f"Unsupported file type: {file_ext}. Please upload a .c, .cpp, .java, or .py file."
            })

        # Handle the code based on the detected language
        try:
            language_config = app.config['SUPPORTED_LANGUAGES'][language]
            exe_file = f"{temp_dir}/solution"

            # Special handling for Java
            classname = None
            if language == 'java':
                # Check if Java is available
                if not os.path.exists(javac_path) and javac_path == 'javac':
                    return jsonify({
                        "status": "error",
                        "phase": "environment",
                        "message": "Java compiler (javac) is not available on this server. Please use C, C++, or Python instead."
                    })

                # Extract class name from Java file
                with open(file_path, 'r') as f:
                    content = f.read()
                    match = re.search(r'public\s+class\s+(\w+)', content)
                    if match:
                        classname = match.group(1)
                    else:
                        return jsonify({
                            "status": "error",
                            "phase": "validation",
                            "message": "Could not find a public class in your Java file."
                        })
                # Make sure the filename matches the class name
                if classname + '.java' != filename:
                    new_file_path = os.path.join(temp_dir, f"{classname}.java")
                    os.rename(file_path, new_file_path)
                    file_path = new_file_path

            # Compile the code if needed
            if language_config['compile_cmd'] is not None:
                compile_cmd = [cmd.format(
                    source_file=file_path,
                    exe_file=exe_file,
                    dir=temp_dir,
                    classname=classname) for cmd in language_config['compile_cmd']]

                print(f"Compiling with command: {compile_cmd}")
                try:
                    compile_result = subprocess.run(
                        compile_cmd,
                        capture_output=True,
                        timeout=30
                    )

                    if compile_result.returncode != 0:
                        error_msg = compile_result.stderr.decode()
                        print(f"Compilation error: {error_msg}")
                        return jsonify({
                            "status": "error",
                            "phase": "compilation",
                            "message": error_msg
                        })
                except FileNotFoundError as e:
                    print(f"Compiler not found: {e}")
                    compiler_name = language_config['compile_cmd'][0].split('/')[-1]
                    return jsonify({
                        "status": "error",
                        "phase": "environment",
                        "message": f"Compiler '{compiler_name}' not found. Please contact the administrator."
                    })

            # Run the tests
            results = []
            test_cases = get_test_cases()

            for test_case in test_cases:
                # Prepare the run command
                run_cmd = [cmd.format(
                    source_file=file_path,
                    exe_file=exe_file,
                    dir=temp_dir,
                    classname=classname) for cmd in language_config['run_cmd']]

                result = run_test_case(run_cmd, test_case, language_config['timeout'])
                results.append(result)

            # Calculate score
            passed = sum(1 for r in results if r["passed"])
            total = len(results)

            return jsonify({
                "status": "success",
                "submission_id": submission_id,
                "language": language,
                "results": results,
                "score": {
                    "passed": passed,
                    "total": total,
                    "percentage": round((passed / total) * 100, 2)
                }
            })

        except subprocess.TimeoutExpired:
            return jsonify({
                "status": "error",
                "phase": "compilation",
                "message": "Compilation timed out after 30 seconds"
            })

        except Exception as e:
            return jsonify({
                "status": "error",
                "phase": "process",
                "message": str(e)
            })

    finally:
        # Schedule cleanup (don't block the response)
        def cleanup():
            time.sleep(300)  # Keep files for 5 minutes for debugging
            shutil.rmtree(temp_dir, ignore_errors=True)

        # In a production app, you'd use a task queue here
        # For simplicity, we're just scheduling deletion after a delay
        # This won't work properly on Render, so you'd need to implement proper cleanup

def run_test_case(run_cmd, test_case, timeout_seconds):
    try:
        # Run with input from test case
        start_time = time.time()
        process = subprocess.run(
            run_cmd,
            input=test_case["input"],
            text=True,
            capture_output=True,
            timeout=timeout_seconds
        )
        execution_time = time.time() - start_time

        # Check if output matches expected
        actual_output = process.stdout
        expected_output = test_case["expected_output"]

        # Normalize line endings and whitespace for comparison
        actual_normalized = actual_output.strip().replace('\r\n', '\n')
        expected_normalized = expected_output.strip().replace('\r\n', '\n')
        passed = actual_normalized == expected_normalized

        return {
            "id": test_case["id"],
            "passed": passed,
            "input": test_case["input"].strip(),
            "expected": test_case["expected_output"].strip(),
            "actual": actual_output.strip(),
            "execution_time": round(execution_time * 1000, 2)  # in milliseconds
        }
    except subprocess.TimeoutExpired:
        return {
            "id": test_case["id"],
            "passed": False,
            "input": test_case["input"].strip(),
            "expected": test_case["expected_output"].strip(),
            "actual": f"Time limit exceeded ({timeout_seconds} seconds)",
            "execution_time": timeout_seconds * 1000  # Convert to ms
        }
    except Exception as e:
        return {
            "id": test_case["id"],
            "passed": False,
            "input": test_case["input"].strip(),
            "expected": test_case["expected_output"].strip(),
            "actual": f"Error: {str(e)}",
            "execution_time": 0
        }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))