#!/usr/bin/env bash
PORT="${PORT:-9099}"
HOST="${HOST:-0.0.0.0}"
# Default value for PIPELINES_DIR
PIPELINES_DIR=${PIPELINES_DIR:-./pipelines}

# Check Python version
check_python_version() {
  if ! command -v python3.11 &> /dev/null; then
    echo "Python 3.11 is required but not found. Please install Python 3.11."
    exit 1
  fi
  
  # Set Python 3.11 as the default Python for this script
  export PYTHON=$(command -v python3.11)
  echo "Using Python: $PYTHON ($(python3.11 --version))"
}

# Run Python version check
check_python_version

# Function to reset pipelines
reset_pipelines_dir() {
  if [ "$RESET_PIPELINES_DIR" = true ]; then
    echo "Resetting pipelines directory: $PIPELINES_DIR"
    if [ -d "$PIPELINES_DIR" ]; then
      rm -rf "${PIPELINES_DIR:?}"/*
      mkdir -p "$PIPELINES_DIR"
      echo "$PIPELINES_DIR has been reset."
    else
      echo "Directory $PIPELINES_DIR does not exist. No action taken."
    fi
  fi
}

# Reset pipelines if needed
reset_pipelines_dir

# Function to install requirements with Poetry
install_requirements() {
  if [[ -f "$1" ]]; then
    echo "requirements.txt found at $1. Installing requirements with Poetry..."
    # Convert requirements.txt to Poetry dependencies
    while IFS= read -r requirement; do
      if [[ ! -z "$requirement" && ! "$requirement" =~ ^# ]]; then
        poetry add "$requirement"
      fi
    done < "$1"
  fi
}

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "Poetry not found. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | $PYTHON -
fi

# Configure Poetry to use Python 3.11
poetry env use python3.11

# Update lock file if needed
if ! poetry check > /dev/null 2>&1; then
    echo "Updating poetry.lock file..."
    poetry lock --no-update
fi

# Install project dependencies with Poetry
poetry install

# Handle additional requirements if specified
if [[ -n "$PIPELINES_REQUIREMENTS_PATH" ]]; then
  install_requirements "$PIPELINES_REQUIREMENTS_PATH"
fi

# Function to download pipeline files
download_pipelines() {
  local path=$1
  local destination=$2
  path=$(echo "$path" | sed 's/^"//;s/"$//')
  
  echo "Downloading pipeline files from $path to $destination..."

  if [[ "$path" =~ ^https://github.com/.*/.*/blob/.* ]]; then
    dest_file=$(basename "$path")
    curl -L "$path?raw=true" -o "$destination/$dest_file"
  elif [[ "$path" =~ ^https://github.com/.*/.*/tree/.* ]]; then
    git_repo=$(echo "$path" | awk -F '/tree/' '{print $1}')
    subdir=$(echo "$path" | awk -F '/tree/' '{print $2}')
    git clone --depth 1 --filter=blob:none --sparse "$git_repo" "$destination"
    (
      cd "$destination" || exit
      git sparse-checkout set "$subdir"
    )
  elif [[ "$path" =~ \.py$ ]]; then
    dest_file=$(basename "$path")
    curl -L "$path" -o "$destination/$dest_file"
  else
    echo "Invalid URL format: $path"
    exit 1
  fi
}

# Function to install requirements from frontmatter
install_frontmatter_requirements() {
  local file=$1
  local first_block=$(cat "$1" | awk '/"""/{flag=!flag; if(flag) count++; if(count == 2) {exit}} flag')
  local requirements=$(echo "$first_block" | grep -i 'requirements:')

  if [ -n "$requirements" ]; then
    requirements=$(echo "$requirements" | awk -F': ' '{print $2}' | tr ',' ' ' | tr -d '\r')
    echo "Installing frontmatter requirements: $requirements"
    poetry add $requirements
  fi
}

# Handle PIPELINES_URLS if specified
if [[ -n "$PIPELINES_URLS" ]]; then
  if [ ! -d "$PIPELINES_DIR" ]; then
    mkdir -p "$PIPELINES_DIR"
  fi

  IFS=';' read -ra ADDR <<< "$PIPELINES_URLS"
  for path in "${ADDR[@]}"; do
    download_pipelines "$path" "$PIPELINES_DIR"
  done

  for file in "$PIPELINES_DIR"/*; do
    if [[ -f "$file" ]]; then
      install_frontmatter_requirements "$file"
    fi
  done
else
  echo "PIPELINES_URLS not specified. Skipping pipelines download and installation."
fi

# Add this function near the top of the file, after the initial variable declarations
check_and_free_port() {
    local port=$1
    if lsof -i ":$port" > /dev/null 2>&1; then
        echo "Port $port is in use. Attempting to free it..."
        lsof -ti ":$port" | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
}

# Check and free port before starting
check_and_free_port $PORT

# Start the server using Poetry and uvicorn
echo "Starting server on $HOST:$PORT..."
if ! poetry run uvicorn main:app --host "$HOST" --port "$PORT" --forwarded-allow-ips '*'; then
    echo "Failed to start server. Please ensure port $PORT is free and try again."
    exit 1
fi
