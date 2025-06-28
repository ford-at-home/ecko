#!/bin/bash

# Echoes FastAPI Lambda Build Script
# Prepares the Lambda deployment package with optimizations

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
CLEAN="false"
VERBOSE="false"
OPTIMIZE="true"

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
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

print_verbose() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}[VERBOSE]${NC} $1"
    fi
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Build Echoes FastAPI Lambda deployment package

OPTIONS:
    -c, --clean              Clean build artifacts before building
    -v, --verbose            Enable verbose output
    --no-optimize            Disable build optimizations
    -h, --help               Show this help message

EXAMPLES:
    # Standard build
    $0

    # Clean build with verbose output
    $0 -c -v

    # Build without optimizations
    $0 --no-optimize

WHAT THIS SCRIPT DOES:
    1. Validates the Python environment
    2. Installs Lambda-specific dependencies
    3. Optimizes the package size
    4. Prepares the build directory
    5. Validates the build
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--clean)
            CLEAN="true"
            shift
            ;;
        -v|--verbose)
            VERBOSE="true"
            shift
            ;;
        --no-optimize)
            OPTIMIZE="false"
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Get script directory and project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_DIR="${BACKEND_DIR}/.aws-sam/build"

print_info "Starting build process..."
print_info "Backend Directory: $BACKEND_DIR"
print_info "Build Directory: $BUILD_DIR"

# Change to backend directory
cd "$BACKEND_DIR"

# Clean build artifacts if requested
if [[ "$CLEAN" == "true" ]]; then
    print_info "Cleaning build artifacts..."
    rm -rf .aws-sam/
    rm -rf __pycache__/
    find . -name "*.pyc" -delete
    find . -name "*.pyo" -delete
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    print_success "Build artifacts cleaned"
fi

# Check prerequisites
print_info "Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
print_verbose "Python version: $PYTHON_VERSION"

if ! command -v pip3 &> /dev/null; then
    print_error "pip3 is not installed"
    exit 1
fi

if ! command -v sam &> /dev/null; then
    print_error "SAM CLI is not installed"
    exit 1
fi

# Validate requirements files
print_info "Validating requirements files..."

if [[ ! -f "requirements-lambda.txt" ]]; then
    print_error "requirements-lambda.txt not found"
    exit 1
fi

if [[ ! -f "template.yaml" ]]; then
    print_error "template.yaml not found"
    exit 1
fi

# Check for app directory
if [[ ! -d "app" ]]; then
    print_error "app directory not found"
    exit 1
fi

# Check for lambda handler
if [[ ! -f "lambda_handler.py" ]]; then
    print_error "lambda_handler.py not found"
    exit 1
fi

print_success "All prerequisites validated"

# Validate Python dependencies
print_info "Validating Python dependencies..."

# Create temporary virtual environment for validation
TEMP_VENV="/tmp/echoes-build-venv-$$"
python3 -m venv "$TEMP_VENV"
source "$TEMP_VENV/bin/activate"

# Install requirements
print_verbose "Installing requirements in temporary environment..."
pip install --quiet -r requirements-lambda.txt

# Test imports
print_verbose "Testing critical imports..."
python3 -c "
try:
    import fastapi
    import mangum
    import boto3
    import pydantic
    print('✓ Critical imports successful')
except ImportError as e:
    print(f'✗ Import error: {e}')
    exit(1)
"

# Test FastAPI app import
print_verbose "Testing FastAPI app import..."
PYTHONPATH="$BACKEND_DIR:$BACKEND_DIR/app" python3 -c "
try:
    from app.main import app
    print('✓ FastAPI app import successful')
except Exception as e:
    print(f'✗ FastAPI app import error: {e}')
    exit(1)
"

deactivate
rm -rf "$TEMP_VENV"

print_success "Python dependencies validated"

# Build with SAM
print_info "Building with SAM CLI..."

SAM_BUILD_ARGS=(
    "build"
    "--use-container"
)

if [[ "$VERBOSE" == "true" ]]; then
    SAM_BUILD_ARGS+=("--debug")
fi

if ! sam "${SAM_BUILD_ARGS[@]}"; then
    print_error "SAM build failed"
    exit 1
fi

print_success "SAM build completed"

# Post-build optimizations
if [[ "$OPTIMIZE" == "true" ]]; then
    print_info "Applying build optimizations..."
    
    LAMBDA_BUILD_DIR="${BUILD_DIR}/EchoesApiFunction"
    
    if [[ -d "$LAMBDA_BUILD_DIR" ]]; then
        cd "$LAMBDA_BUILD_DIR"
        
        # Remove unnecessary files to reduce package size
        print_verbose "Removing unnecessary files..."
        
        # Remove test files
        find . -name "*test*" -type f -delete 2>/dev/null || true
        find . -name "*_test.py" -delete 2>/dev/null || true
        find . -name "test_*.py" -delete 2>/dev/null || true
        
        # Remove documentation
        find . -name "*.md" -delete 2>/dev/null || true
        find . -name "*.rst" -delete 2>/dev/null || true
        find . -name "*.txt" -delete 2>/dev/null || true
        
        # Remove development files
        find . -name "*.dev" -delete 2>/dev/null || true
        find . -name ".git*" -delete 2>/dev/null || true
        
        # Remove __pycache__ directories
        find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        
        # Remove .pyc and .pyo files
        find . -name "*.pyc" -delete 2>/dev/null || true
        find . -name "*.pyo" -delete 2>/dev/null || true
        
        # Remove large unnecessary packages if present
        rm -rf boto3/examples/ 2>/dev/null || true
        rm -rf botocore/data/endpoints.json 2>/dev/null || true
        rm -rf numpy/tests/ 2>/dev/null || true
        rm -rf pandas/tests/ 2>/dev/null || true
        
        print_verbose "Optimization completed"
        
        cd "$BACKEND_DIR"
    else
        print_warning "Lambda build directory not found, skipping optimizations"
    fi
fi

# Validate the build
print_info "Validating build..."

if [[ ! -d "$BUILD_DIR" ]]; then
    print_error "Build directory not created"
    exit 1
fi

if [[ ! -d "${BUILD_DIR}/EchoesApiFunction" ]]; then
    print_error "Lambda function build not found"
    exit 1
fi

# Check for critical files in the build
LAMBDA_BUILD_DIR="${BUILD_DIR}/EchoesApiFunction"
CRITICAL_FILES=(
    "lambda_handler.py"
    "app/main.py"
    "app/core/config.py"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [[ ! -f "${LAMBDA_BUILD_DIR}/${file}" ]]; then
        print_error "Critical file missing in build: $file"
        exit 1
    fi
    print_verbose "✓ Found critical file: $file"
done

# Calculate build size
BUILD_SIZE=$(du -sh "$LAMBDA_BUILD_DIR" | cut -f1)
print_info "Build size: $BUILD_SIZE"

# Check if build size is reasonable for Lambda
BUILD_SIZE_BYTES=$(du -s "$LAMBDA_BUILD_DIR" | cut -f1)
BUILD_SIZE_MB=$((BUILD_SIZE_BYTES / 1024))

if (( BUILD_SIZE_MB > 200 )); then
    print_warning "Build size is large (${BUILD_SIZE_MB}MB). Consider optimizing dependencies."
    print_warning "Lambda has a 250MB limit for deployment packages."
elif (( BUILD_SIZE_MB > 50 )); then
    print_warning "Build size is moderate (${BUILD_SIZE_MB}MB). Monitor cold start performance."
else
    print_success "Build size is good (${BUILD_SIZE_MB}MB)"
fi

# Test the lambda handler
print_info "Testing Lambda handler..."

cd "$LAMBDA_BUILD_DIR"
PYTHONPATH="." python3 -c "
import json
from lambda_handler import lambda_handler

# Test event
test_event = {
    'httpMethod': 'GET',
    'path': '/health',
    'headers': {},
    'queryStringParameters': None,
    'body': None,
    'requestContext': {
        'identity': {'sourceIp': '127.0.0.1'}
    }
}

# Mock context
class MockContext:
    def __init__(self):
        self.aws_request_id = 'test-request-id'
        self.function_name = 'test-function'
        self.function_version = '1'

try:
    context = MockContext()
    response = lambda_handler(test_event, context)
    print('✓ Lambda handler test successful')
    print(f'  Status Code: {response.get(\"statusCode\", \"unknown\")}')
except Exception as e:
    print(f'✗ Lambda handler test failed: {e}')
    exit(1)
"

cd "$BACKEND_DIR"

print_success "Build validation completed successfully!"
echo
print_success "Build Summary:"
print_info "  Build directory: $BUILD_DIR"
print_info "  Lambda function: ${BUILD_DIR}/EchoesApiFunction"
print_info "  Build size: $BUILD_SIZE"
print_info "  Optimizations: $([ "$OPTIMIZE" == "true" ] && echo "enabled" || echo "disabled")"
echo
print_info "You can now deploy using: ./scripts/deploy.sh"