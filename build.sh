#!/usr/bin/env bash

# Exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p uploads
mkdir -p test_cases
mkdir -p templates

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

# Ensure the index.html file exists in templates
if [ ! -f "templates/index.html" ]; then
  echo "Warning: templates/index.html not found!"
fi