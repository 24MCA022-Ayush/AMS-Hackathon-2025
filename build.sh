#!/usr/bin/env bash

# Exit on error after setup (but allow download retries)
set -o errexit

echo "Installing Java (self-contained)..."

JDK_URL="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.14%2B7/OpenJDK17U-jdk_x64_linux_hotspot_17.0.14_7.tar.gz" # VERIFY URL IS STILL CORRECT!
JDK_DIR="vendor/java"
MAX_RETRIES=3
RETRY_DELAY=5  # seconds

mkdir -p vendor
mkdir -p "$JDK_DIR"

download_jdk() {
  local retry_count=0
  while [ $retry_count -lt $MAX_RETRIES ]; do
    echo "Attempting JDK download (attempt $((retry_count + 1)) of $MAX_RETRIES)..."
    wget -q "$JDK_URL" -O jdk.tar.gz && return 0  # Download and exit function on success
    retry_count=$((retry_count + 1))
    echo "Download failed. Retrying in $RETRY_DELAY seconds..."
    sleep "$RETRY_DELAY"
  done
  echo "Max download retries exceeded. Aborting build."
  return 1  # Return non-zero exit code if all retries fail
}

if ! download_jdk; then
  exit 1  # Abort build if JDK download fails after retries
fi

if ! tar -xzf jdk.tar.gz -C "$JDK_DIR" --strip-components=1; then
  echo "Error extracting JDK archive. Aborting build."
  rm jdk.tar.gz # Clean up potentially corrupted archive
  exit 1
fi
rm jdk.tar.gz # Clean up archive after successful extraction

# Set JAVA_HOME and PATH
export JAVA_HOME="$JDK_DIR"
export PATH="$JAVA_HOME/bin:$PATH"

# Verify Java installation (optional, but good for debugging)
java -version
javac -version

echo "Upgrading pip..."  # Add this line to upgrade pip
/opt/render/project/src/.venv/bin/python3.9 -m pip install --upgrade pip

# Install Python dependencies (rest of your script)
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

# Save Java paths to a config file
cat > config/java_paths.json << EOL
{
  "java_path": "$JAVA_PATH",
  "javac_path": "$JAVAC_PATH"
}
EOL

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

# Create necessary directories (again, likely redundant but harmless)
mkdir -p uploads
mkdir -p test_cases

# Create test cases file if it doesn't exist (redundant, but harmless)
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

# Create templates directory and index.html (redundant, but harmless)
mkdir -p templates