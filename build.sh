# build.sh
#!/usr/bin/env bash

# Exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p uploads
mkdir -p test_cases
mkdir -p templates
mkdir -p config

# Find Java paths and save them
echo "Checking for Java installation..."
JAVA_PATH=$(which java 2>/dev/null || echo "")
JAVAC_PATH=$(which javac 2>/dev/null || echo "")

echo "Java path: $JAVA_PATH"
echo "JavaC path: $JAVAC_PATH"

# Save Java paths to a config file that our app can read
cat > config/java_paths.json << EOL
{
  "java_path": "$JAVA_PATH",
  "javac_path": "$JAVAC_PATH"
}
EOL

# Try to find alternative Java paths
echo "Looking for alternative Java paths..."
find / -name "java" -type f -executable 2>/dev/null | grep -v "tmp" > config/alt_java_paths.txt
find / -name "javac" -type f -executable 2>/dev/null | grep -v "tmp" > config/alt_javac_paths.txt

# Create test cases file if it doesn't exist
if [ ! -f "test_cases/test_cases.json" ]; then
  cat > test_cases/test_cases.json << 'EOL'
[
  {
    "id": "1",
    "input": "5 7\n",
    "expected_output": "12\n"
  },
  {
    "id": "2",
    "input": "10 20\n",
    "expected_output": "30\n"
  },
  {
    "id": "3",
    "input": "0 0\n",
    "expected_output": "0\n"
  },
  {
    "id": "4",
    "input": "-5 10\n",
    "expected_output": "5\n"
  },
  {
    "id": "5",
    "input": "100 -30\n",
    "expected_output": "70\n"
  }
]
EOL
fi

# Create necessary directories
mkdir -p uploads
mkdir -p test_cases

# Create test cases file if it doesn't exist
if [ ! -f "test_cases/test_cases.json" ]; then
  cat > test_cases/test_cases.json << 'EOL'
[
  {
    "id": "1",
    "input": "5 7\n",
    "expected_output": "12\n"
  },
  {
    "id": "2",
    "input": "10 20\n",
    "expected_output": "30\n"
  },
  {
    "id": "3",
    "input": "0 0\n",
    "expected_output": "0\n"
  },
  {
    "id": "4",
    "input": "-5 10\n",
    "expected_output": "5\n"
  },
  {
    "id": "5",
    "input": "100 -30\n",
    "expected_output": "70\n"
  }
]
EOL
fi

# Create templates directory and index.html
mkdir -p templates