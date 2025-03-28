#!/usr/bin/env bash



echo "Installing Java (self-contained)..."

# Define JDK download URL (Adoptium Temurin 17 Linux x64, replace with latest if needed)
JDK_URL="https://download.adoptium.net/temurin17/releases/latest/jdk-17.0.10+7/temurin17-jdk-linux-x64.tar.gz"
JDK_DIR="vendor/java"  # Directory to extract JDK to

mkdir -p vendor  # Create vendor directory if it doesn't exist
mkdir -p "$JDK_DIR"

wget -q "$JDK_URL" -O jdk.tar.gz  # Download JDK silently
tar -xzf jdk.tar.gz -C "$JDK_DIR" --strip-components=1 # Extract to vendor/java, remove top level dir
rm jdk.tar.gz # Clean up the downloaded archive

# Set JAVA_HOME and PATH environment variables
export JAVA_HOME="$JDK_DIR"
export PATH="$JAVA_HOME/bin:$PATH"

# Verify Java installation (optional, but good for debugging)
java -version
javac -version

# Install Python dependencies (rest of your script is the same from here)
pip install -r requirements.txt

# Create necessary directories
mkdir -p uploads
mkdir -p test_cases
mkdir -p templates
mkdir -p config

# Find Java paths and save them (now using the extracted JDK)
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

# Create test cases file if it doesn't exist (rest of your script is the same from here)
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

# Create necessary directories (again, rest of your script is the same from here, these are likely redundant)
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