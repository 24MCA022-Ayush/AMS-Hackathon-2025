from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, session
import os
import subprocess
import tempfile
import uuid
import json
import time
import re
from werkzeug.utils import secure_filename
import shutil
from flask_session import Session  # Import Flask-Session


# --- Firebase Admin SDK ---
import firebase_admin
from firebase_admin import credentials
from firebase_admin import auth # Import auth  <--- ENSURE THIS LINE IS PRESENT AND CORRECT
from firebase_admin import db

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key_here') # Good practice to set secret key
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['TEST_CASES_FOLDER'] = 'test_cases'
app.config['CONFIG_FOLDER'] = 'config'
app.config["SESSION_PERMANENT"] = False  # Session cookies are not permanent
app.config["SESSION_TYPE"] = "filesystem"  # Use filesystem for sessions
Session(app) # Initialize Flask-Session

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
users_data_ref = db.reference('/usersData')

@app.route('/', methods=['GET', 'POST']) # Allow POST for login submission
def login_page():
    if request.method == 'POST':
        team_name = request.form.get('team-name')
        entry_code = request.form.get('entry-code')

        try:
            print(f"[/login] Attempting login for team: {team_name}") # Debug log
            user = auth.sign_in_with_email_and_password(f"{team_name}@hackathon.ams", entry_code)
            print(f"[/login] Login successful for user: {user['email']}") # Debug log
            session['user_uid'] = user['localId']
            print(f"[/login] User UID set in session: {session['user_uid']}") # Debug log
            return redirect(url_for('hackathon_page'))
        except Exception as e:
            error_message = str(e)
            print(f"[/login] Login failed: {e}") # Debug log
            return render_template('index.html', login_error=error_message)
    print("[/login] Serving login page (GET request).") # Debug log
    return render_template('index.html', login_error=None)

@app.route('/hackathon')
def hackathon_page():
    user_uid = session.get('user_uid')
    print(f"[/hackathon] User UID from session: {user_uid}") # Debug log

    if not user_uid:
        print("[/hackathon] No user_uid in session, redirecting to login.") # Debug log
        return redirect(url_for('login_page'))

    try:
        print("[/hackathon] Attempting to fetch challenge data from Firebase...") # Debug log
        challenge_data = challenge_data_ref.get()
        print(f"[/hackathon] Challenge data fetched: {challenge_data}") # Debug log
        if challenge_data:
            return render_template('hackathon.html', challenge_data=challenge_data)
        else:
            print("[/hackathon] Error: Challenge data is None (not found or empty).") # Debug log
            return "Error: Challenge data not found in Firebase.", 500
    except Exception as e:
        print(f"[/hackathon] Exception while fetching challenge data: {e}") # Debug log
        return f"Error fetching challenge data from Firebase: {e}", 500

@app.route('/logout') # Optional logout route
def logout():
    session.pop('user_uid', None) # Clear user session
    return redirect(url_for('login_page')) # Redirect to login page after logout


@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

def get_test_cases():
    test_cases_file = os.path.join(app.config['TEST_CASES_FOLDER'], 'test_cases.json')
    with open(test_cases_file, 'r') as f:
        return json.load(f)

@app.route('/api/submit', methods=['POST'])
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