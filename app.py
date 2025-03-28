from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import subprocess
import tempfile
import uuid
import json
import time
from werkzeug.utils import secure_filename
import shutil

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['TEST_CASES_FOLDER'] = 'test_cases'

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

@app.route('/')
def index():
    return render_template('index.html')

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
        
        # Handle C++ files
        if filename.endswith('.cpp'):
            # Compile the code
            try:
                compile_result = subprocess.run(
                    ["g++", "-std=c++17", file_path, "-o", f"{temp_dir}/solution"],
                    capture_output=True,
                    timeout=30
                )
                
                if compile_result.returncode != 0:
                    return jsonify({
                        "status": "error",
                        "phase": "compilation",
                        "message": compile_result.stderr.decode()
                    })
                
                # Run the tests
                results = []
                test_cases = get_test_cases()
                
                for test_case in test_cases:
                    result = run_test_case(f"{temp_dir}/solution", test_case)
                    results.append(result)
                
                # Calculate score
                passed = sum(1 for r in results if r["passed"])
                total = len(results)
                
                return jsonify({
                    "status": "success",
                    "submission_id": submission_id,
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
        else:
            return jsonify({
                "status": "error",
                "phase": "validation",
                "message": "Unsupported file type. Please upload a .cpp file."
            })
            
    finally:
        # Schedule cleanup (don't block the response)
        def cleanup():
            time.sleep(300)  # Keep files for 5 minutes for debugging
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        # In a production app, you'd use a task queue here
        # For simplicity, we're just scheduling deletion after a delay
        # This won't work properly on Render, so you'd need to implement proper cleanup

def run_test_case(executable_path, test_case):
    try:
        # Run with input from test case
        start_time = time.time()
        process = subprocess.run(
            [executable_path],
            input=test_case["input"],
            text=True,
            capture_output=True,
            timeout=5  # 5 second timeout
        )
        execution_time = time.time() - start_time
        
        # Check if output matches expected
        actual_output = process.stdout
        expected_output = test_case["expected_output"]
        passed = actual_output == expected_output
        
        return {
            "id": test_case["id"],
            "passed": passed,
            "input": test_case["input"].strip(),
            "expected": expected_output.strip(),
            "actual": actual_output.strip(),
            "execution_time": round(execution_time * 1000, 2)  # in milliseconds
        }
    except subprocess.TimeoutExpired:
        return {
            "id": test_case["id"],
            "passed": False,
            "input": test_case["input"].strip(),
            "expected": test_case["expected_output"].strip(),
            "actual": "Time limit exceeded (5 seconds)",
            "execution_time": 5000  # 5000 ms
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
