#!/bin/bash

# Comprehensive test runner for Echoes Audio Time Machine
# Runs all test suites and generates consolidated reports

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_RESULTS_DIR="$PROJECT_ROOT/test-results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_DIR="$TEST_RESULTS_DIR/consolidated_$TIMESTAMP"

# Test configuration
RUN_UNIT_TESTS=true
RUN_INTEGRATION_TESTS=true
RUN_E2E_TESTS=true
RUN_PERFORMANCE_TESTS=false  # Disabled by default (resource intensive)
RUN_SECURITY_TESTS=true
GENERATE_COVERAGE=true
PARALLEL_EXECUTION=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --no-unit)
      RUN_UNIT_TESTS=false
      shift
      ;;
    --no-integration)
      RUN_INTEGRATION_TESTS=false
      shift
      ;;
    --no-e2e)
      RUN_E2E_TESTS=false
      shift
      ;;
    --with-performance)
      RUN_PERFORMANCE_TESTS=true
      shift
      ;;
    --no-security)
      RUN_SECURITY_TESTS=false
      shift
      ;;
    --no-coverage)
      GENERATE_COVERAGE=false
      shift
      ;;
    --sequential)
      PARALLEL_EXECUTION=false
      shift
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  --no-unit           Skip unit tests"
      echo "  --no-integration    Skip integration tests"
      echo "  --no-e2e           Skip end-to-end tests"
      echo "  --with-performance  Include performance tests"
      echo "  --no-security      Skip security tests"
      echo "  --no-coverage      Skip coverage generation"
      echo "  --sequential       Run tests sequentially"
      echo "  --help             Show this help"
      exit 0
      ;;
    *)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

# Utility functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create test results directory
create_test_dirs() {
    log_info "Creating test result directories..."
    mkdir -p "$REPORT_DIR"/{backend,frontend,e2e,performance,security,coverage}
    mkdir -p "$TEST_RESULTS_DIR"/{backend,frontend,e2e,performance,security}
}

# Environment setup
setup_environment() {
    log_info "Setting up test environment..."
    
    # Ensure required environment variables
    export NODE_ENV=test
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    export TEST_DATABASE_URL="sqlite:///test.db"
    export AWS_ACCESS_KEY_ID="testing"
    export AWS_SECRET_ACCESS_KEY="testing"
    export AWS_SECURITY_TOKEN="testing"
    export AWS_SESSION_TOKEN="testing"
    export AWS_DEFAULT_REGION="us-east-1"
    
    # Clean up previous test artifacts
    rm -rf "$PROJECT_ROOT/.pytest_cache"
    rm -rf "$PROJECT_ROOT/node_modules/.cache"
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."
    
    if [ -f "$PROJECT_ROOT/package.json" ]; then
        cd "$PROJECT_ROOT"
        npm ci --silent
    fi
    
    if [ -f "$PROJECT_ROOT/requirements-test.txt" ]; then
        pip install -r requirements-test.txt --quiet
    elif [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        pip install -r requirements.txt --quiet
    fi
    
    # Install additional test dependencies
    pip install pytest pytest-asyncio pytest-cov pytest-html pytest-xdist --quiet
}

# Run backend unit tests
run_backend_tests() {
    if [ "$RUN_UNIT_TESTS" != true ]; then
        log_warning "Skipping backend unit tests"
        return 0
    fi
    
    log_info "Running backend unit tests..."
    cd "$PROJECT_ROOT"
    
    local pytest_args="tests/backend -m 'unit' --junitxml=$TEST_RESULTS_DIR/backend/junit.xml"
    
    if [ "$GENERATE_COVERAGE" = true ]; then
        pytest_args="$pytest_args --cov=app --cov-report=html:$TEST_RESULTS_DIR/backend/coverage"
    fi
    
    if [ "$PARALLEL_EXECUTION" = true ]; then
        pytest_args="$pytest_args -n auto"
    fi
    
    if python -m pytest $pytest_args; then
        log_success "Backend unit tests passed"
        return 0
    else
        log_error "Backend unit tests failed"
        return 1
    fi
}

# Run frontend component tests
run_frontend_tests() {
    if [ "$RUN_UNIT_TESTS" != true ]; then
        log_warning "Skipping frontend component tests"
        return 0
    fi
    
    log_info "Running frontend component tests..."
    cd "$PROJECT_ROOT"
    
    local jest_args="--config tests/jest.config.js --outputFile=$TEST_RESULTS_DIR/frontend/results.json"
    
    if [ "$GENERATE_COVERAGE" = true ]; then
        jest_args="$jest_args --coverage --coverageDirectory=$TEST_RESULTS_DIR/frontend/coverage"
    fi
    
    if [ "$PARALLEL_EXECUTION" != true ]; then
        jest_args="$jest_args --runInBand"
    fi
    
    if npm test -- $jest_args; then
        log_success "Frontend component tests passed"
        return 0
    else
        log_error "Frontend component tests failed"
        return 1
    fi
}

# Run integration tests
run_integration_tests() {
    if [ "$RUN_INTEGRATION_TESTS" != true ]; then
        log_warning "Skipping integration tests"
        return 0
    fi
    
    log_info "Running integration tests..."
    cd "$PROJECT_ROOT"
    
    local pytest_args="tests/integration -m 'integration' --junitxml=$TEST_RESULTS_DIR/backend/integration-junit.xml"
    
    if [ "$PARALLEL_EXECUTION" = true ]; then
        pytest_args="$pytest_args -n auto"
    fi
    
    if python -m pytest $pytest_args; then
        log_success "Integration tests passed"
        return 0
    else
        log_error "Integration tests failed"
        return 1
    fi
}

# Run end-to-end tests
run_e2e_tests() {
    if [ "$RUN_E2E_TESTS" != true ]; then
        log_warning "Skipping end-to-end tests"
        return 0
    fi
    
    log_info "Running end-to-end tests..."
    cd "$PROJECT_ROOT"
    
    # Install Playwright browsers if needed
    if command -v npx >/dev/null 2>&1; then
        npx playwright install --with-deps
    fi
    
    local playwright_args="--config tests/playwright.config.js"
    
    if [ "$PARALLEL_EXECUTION" != true ]; then
        playwright_args="$playwright_args --workers=1"
    fi
    
    if npx playwright test $playwright_args; then
        log_success "End-to-end tests passed"
        return 0
    else
        log_error "End-to-end tests failed"
        return 1
    fi
}

# Run performance tests
run_performance_tests() {
    if [ "$RUN_PERFORMANCE_TESTS" != true ]; then
        log_warning "Skipping performance tests"
        return 0
    fi
    
    log_info "Running performance tests..."
    cd "$PROJECT_ROOT"
    
    local pytest_args="tests/performance -m 'performance' --junitxml=$TEST_RESULTS_DIR/performance/junit.xml"
    
    if python -m pytest $pytest_args; then
        log_success "Performance tests completed"
        return 0
    else
        log_warning "Performance tests failed or performance degraded"
        return 1
    fi
}

# Run security tests
run_security_tests() {
    if [ "$RUN_SECURITY_TESTS" != true ]; then
        log_warning "Skipping security tests"
        return 0
    fi
    
    log_info "Running security tests..."
    cd "$PROJECT_ROOT"
    
    local pytest_args="tests/security -m 'security' --junitxml=$TEST_RESULTS_DIR/security/junit.xml"
    
    if python -m pytest $pytest_args; then
        log_success "Security tests passed"
        return 0
    else
        log_error "Security vulnerabilities detected"
        return 1
    fi
}

# Generate consolidated report
generate_report() {
    log_info "Generating consolidated test report..."
    
    # Copy all test results to consolidated directory
    if [ -d "$TEST_RESULTS_DIR/backend" ]; then
        cp -r "$TEST_RESULTS_DIR/backend"/* "$REPORT_DIR/backend/" 2>/dev/null || true
    fi
    
    if [ -d "$TEST_RESULTS_DIR/frontend" ]; then
        cp -r "$TEST_RESULTS_DIR/frontend"/* "$REPORT_DIR/frontend/" 2>/dev/null || true
    fi
    
    if [ -d "$TEST_RESULTS_DIR/e2e" ]; then
        cp -r "$TEST_RESULTS_DIR/e2e"/* "$REPORT_DIR/e2e/" 2>/dev/null || true
    fi
    
    if [ -d "$TEST_RESULTS_DIR/performance" ]; then
        cp -r "$TEST_RESULTS_DIR/performance"/* "$REPORT_DIR/performance/" 2>/dev/null || true
    fi
    
    if [ -d "$TEST_RESULTS_DIR/security" ]; then
        cp -r "$TEST_RESULTS_DIR/security"/* "$REPORT_DIR/security/" 2>/dev/null || true
    fi
    
    # Generate summary report
    cat > "$REPORT_DIR/summary.html" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Echoes Test Summary - $TIMESTAMP</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .success { background-color: #d4edda; }
        .warning { background-color: #fff3cd; }
        .error { background-color: #f8d7da; }
        .link { color: #007bff; text-decoration: none; }
        .link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Echoes Audio Time Machine - Test Summary</h1>
        <p>Generated: $TIMESTAMP</p>
        <p>Test Environment: $NODE_ENV</p>
    </div>
    
    <div class="section">
        <h2>Test Suite Results</h2>
        <ul>
            <li>Backend Unit Tests: <a href="backend/report.html" class="link">View Report</a></li>
            <li>Frontend Component Tests: <a href="frontend/report.html" class="link">View Report</a></li>
            <li>Integration Tests: <a href="backend/integration-report.html" class="link">View Report</a></li>
            <li>End-to-End Tests: <a href="e2e/html-report/index.html" class="link">View Report</a></li>
            <li>Performance Tests: <a href="performance/report.html" class="link">View Report</a></li>
            <li>Security Tests: <a href="security/report.html" class="link">View Report</a></li>
        </ul>
    </div>
    
    <div class="section">
        <h2>Coverage Reports</h2>
        <ul>
            <li>Backend Coverage: <a href="backend/coverage/index.html" class="link">View Coverage</a></li>
            <li>Frontend Coverage: <a href="frontend/coverage/lcov-report/index.html" class="link">View Coverage</a></li>
        </ul>
    </div>
</body>
</html>
EOF
    
    log_success "Consolidated report generated at: $REPORT_DIR/summary.html"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up test environment..."
    
    # Kill any background processes
    pkill -f "test-server" 2>/dev/null || true
    
    # Clean up temporary files
    rm -f test.db* 2>/dev/null || true
}

# Main execution
main() {
    local exit_code=0
    
    log_info "Starting comprehensive test suite for Echoes Audio Time Machine"
    log_info "Timestamp: $TIMESTAMP"
    
    # Setup
    create_test_dirs
    setup_environment
    install_dependencies
    
    # Set up cleanup trap
    trap cleanup EXIT
    
    # Run test suites
    run_backend_tests || exit_code=$?
    run_frontend_tests || exit_code=$?
    run_integration_tests || exit_code=$?
    run_e2e_tests || exit_code=$?
    run_performance_tests || exit_code=$?
    run_security_tests || exit_code=$?
    
    # Generate reports
    generate_report
    
    # Final summary
    if [ $exit_code -eq 0 ]; then
        log_success "All enabled test suites passed successfully!"
        log_info "View the complete report at: $REPORT_DIR/summary.html"
    else
        log_error "Some tests failed. Check the detailed reports for more information."
        log_info "Partial report available at: $REPORT_DIR/summary.html"
    fi
    
    exit $exit_code
}

# Run main function
main "$@"