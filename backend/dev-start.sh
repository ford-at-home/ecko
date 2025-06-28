#!/bin/bash
# Echoes API Local Development Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PORT=8000
RELOAD=true
LOG_LEVEL=info
CHECK_DEPS=true

# Function to print colored output
print_status() {
    echo -e "${BLUE}[Echoes API]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python() {
    if ! command_exists python3; then
        print_error "Python 3 is not installed. Please install Python 3.11 or higher."
        exit 1
    fi
    
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    required_version="3.11"
    
    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
        print_error "Python $python_version found, but Python $required_version+ is required."
        exit 1
    fi
    
    print_success "Python $python_version found"
}

# Function to check and create virtual environment
check_venv() {
    if [ ! -d "venv" ]; then
        print_status "Creating virtual environment..."
        python3 -m venv venv
        print_success "Virtual environment created"
    fi
    
    print_status "Activating virtual environment..."
    source venv/bin/activate
    print_success "Virtual environment activated"
}

# Function to install dependencies
check_dependencies() {
    if [ "$CHECK_DEPS" = true ]; then
        print_status "Checking dependencies..."
        
        # Check if requirements.txt exists
        if [ ! -f "requirements.txt" ]; then
            print_error "requirements.txt not found!"
            exit 1
        fi
        
        # Install or upgrade pip
        print_status "Upgrading pip..."
        pip install --upgrade pip
        
        # Install dependencies
        print_status "Installing dependencies..."
        pip install -r requirements.txt
        
        print_success "Dependencies installed"
    fi
}

# Function to check environment configuration
check_environment() {
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            print_warning "No .env file found. Copying from .env.example..."
            cp .env.example .env
            print_warning "Please edit .env with your configuration before continuing."
            print_status "Opening .env file for editing..."
            if command_exists code; then
                code .env
            elif command_exists nano; then
                nano .env
            elif command_exists vim; then
                vim .env
            else
                print_warning "Please manually edit .env file"
            fi
            read -p "Press Enter to continue after editing .env..."
        else
            print_error "No .env file or .env.example found!"
            exit 1
        fi
    fi
    
    print_success "Environment configuration found"
}

# Function to check system dependencies
check_system_deps() {
    print_status "Checking system dependencies..."
    
    # Check for ffmpeg (for audio processing)
    if ! command_exists ffmpeg; then
        print_warning "ffmpeg not found. Audio processing may not work properly."
        print_status "To install ffmpeg:"
        print_status "  macOS: brew install ffmpeg"
        print_status "  Ubuntu/Debian: sudo apt-get install ffmpeg"
        print_status "  Windows: Download from https://ffmpeg.org/download.html"
    else
        print_success "ffmpeg found"
    fi
    
    # Check for Redis (optional, for production features)
    if ! command_exists redis-server; then
        print_warning "Redis not found. Rate limiting will use in-memory storage."
        print_status "To install Redis:"
        print_status "  macOS: brew install redis"
        print_status "  Ubuntu/Debian: sudo apt-get install redis-server"
    else
        print_success "Redis found"
    fi
}

# Function to run health checks
run_health_checks() {
    print_status "Running health checks..."
    
    # Check if we can import the main application
    if python3 -c "from app.main import app; print('Application import successful')" 2>/dev/null; then
        print_success "Application imports successfully"
    else
        print_error "Failed to import application. Check your code for errors."
        exit 1
    fi
}

# Function to start the server
start_server() {
    print_status "Starting Echoes API server..."
    print_status "Port: $PORT"
    print_status "Reload: $RELOAD"
    print_status "Log Level: $LOG_LEVEL"
    print_status ""
    print_status "API will be available at: http://localhost:$PORT"
    print_status "API Documentation: http://localhost:$PORT/docs"
    print_status "Health Check: http://localhost:$PORT/health"
    print_status ""
    print_status "Press Ctrl+C to stop the server"
    print_status "================================"
    
    # Start the server using uvicorn
    python3 -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port $PORT \
        --reload=$RELOAD \
        --log-level $LOG_LEVEL
}

# Function to show help
show_help() {
    echo "Echoes API Development Startup Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -p, --port PORT       Port to run server on (default: 8000)"
    echo "  -n, --no-reload       Disable auto-reload"
    echo "  -l, --log-level LEVEL Log level (default: info)"
    echo "  -s, --skip-deps       Skip dependency installation"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Start with default settings"
    echo "  $0 -p 8080           # Start on port 8080"
    echo "  $0 --no-reload       # Start without auto-reload"
    echo "  $0 -l debug          # Start with debug logging"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -n|--no-reload)
            RELOAD=false
            shift
            ;;
        -l|--log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        -s|--skip-deps)
            CHECK_DEPS=false
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
print_status "Echoes API Development Setup"
print_status "=============================="

# Run all checks
check_python
check_venv
check_dependencies
check_environment
check_system_deps
run_health_checks

# Start the server
start_server