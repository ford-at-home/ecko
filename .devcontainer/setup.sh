#!/bin/bash

set -e

echo "🌀 Setting up Echoes development environment in Codespaces..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Update system packages
echo -e "${BLUE}📦 Updating system packages...${NC}"
sudo apt-get update

# Install additional system dependencies
echo -e "${BLUE}🔧 Installing system dependencies...${NC}"
sudo apt-get install -y \
    curl \
    wget \
    git \
    jq \
    postgresql-client \
    redis-tools \
    unzip

# Install AWS CLI if not already installed
if ! command -v aws &> /dev/null; then
    echo -e "${BLUE}☁️  Installing AWS CLI...${NC}"
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install
    rm -rf aws awscliv2.zip
fi

# Install AWS CDK
echo -e "${BLUE}🏗️  Installing AWS CDK...${NC}"
npm install -g aws-cdk

# Install SAM CLI
if ! command -v sam &> /dev/null; then
    echo -e "${BLUE}🚀 Installing AWS SAM CLI...${NC}"
    wget https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip
    unzip aws-sam-cli-linux-x86_64.zip -d sam-installation
    sudo ./sam-installation/install
    rm -rf sam-installation aws-sam-cli-linux-x86_64.zip
fi

# Install Expo CLI for React Native development
echo -e "${BLUE}📱 Installing Expo CLI...${NC}"
npm install -g @expo/cli eas-cli

# Install Python development tools
echo -e "${BLUE}🐍 Installing Python development tools...${NC}"
pip install --user \
    black \
    flake8 \
    isort \
    mypy \
    pytest \
    pytest-cov \
    pytest-asyncio \
    fastapi \
    uvicorn

# Install Node.js project dependencies
echo -e "${BLUE}📦 Installing Node.js dependencies...${NC}"
npm install

# Install pre-commit hooks (if available)
if [ -f ".pre-commit-config.yaml" ]; then
    echo -e "${BLUE}🔗 Installing pre-commit hooks...${NC}"
    pip install --user pre-commit
    pre-commit install
fi

# Set up Git configuration
echo -e "${BLUE}📝 Configuring Git...${NC}"
git config --global init.defaultBranch main
git config --global pull.rebase false
git config --global core.autocrlf input

# Create necessary directories
echo -e "${BLUE}📁 Creating project directories...${NC}"
mkdir -p tmp/localstack/data
mkdir -p tmp/sam-local
mkdir -p logs
mkdir -p coverage

# Set up local environment file
echo -e "${BLUE}⚙️  Setting up local environment...${NC}"
if [ ! -f .env.local ]; then
    cat > .env.local << EOF
# Codespaces Development Environment Variables
ENVIRONMENT=dev
DEBUG=1
LOCALSTACK_VOLUME_DIR=./tmp/localstack

# Database
POSTGRES_DB=echoes_dev
POSTGRES_USER=echoes_user
POSTGRES_PASSWORD=echoes_password

# LocalStack
LOCALSTACK_ENDPOINT=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1

# API
API_PORT=8000
FRONTEND_PORT=3000

# Development
CODESPACES=true
GITHUB_CODESPACES=true
EOF
fi

# Set up AWS CLI configuration for LocalStack
echo -e "${BLUE}☁️  Configuring AWS CLI for LocalStack...${NC}"
mkdir -p ~/.aws
cat > ~/.aws/config << EOF
[default]
region = us-east-1
output = json

[profile localstack]
region = us-east-1
output = json
endpoint_url = http://localhost:4566
EOF

cat > ~/.aws/credentials << EOF
[default]
aws_access_key_id = test
aws_secret_access_key = test

[localstack]
aws_access_key_id = test
aws_secret_access_key = test
EOF

# Set up shell aliases for development
echo -e "${BLUE}🔧 Setting up development aliases...${NC}"
cat >> ~/.bashrc << EOF

# Echoes Development Aliases
alias start-local='./scripts/local-dev/start-local.sh'
alias stop-local='./scripts/local-dev/stop-local.sh'
alias test-local='./scripts/local-dev/test-local.sh'
alias logs-local='docker-compose -f docker-compose.local.yml logs -f'
alias awslocal='aws --endpoint-url=http://localhost:4566'

# Quick commands
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias ..='cd ..'
alias ...='cd ../..'

# Git aliases
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git log --oneline'

# Development shortcuts
alias serve='npm run dev'
alias build='npm run build'
alias test='npm test'
alias lint='npm run lint'

echo "🌀 Echoes development environment ready!"
echo "💡 Available commands:"
echo "  start-local  - Start local development services"
echo "  stop-local   - Stop local development services"
echo "  test-local   - Test local environment"
echo "  serve        - Start frontend development server"
echo "  awslocal     - AWS CLI configured for LocalStack"
EOF

# Make scripts executable
echo -e "${BLUE}🔐 Making scripts executable...${NC}"
find scripts/ -name "*.sh" -exec chmod +x {} \;
chmod +x claude-flow

# Install VS Code extensions (if not already installed)
echo -e "${BLUE}🔌 Installing VS Code extensions...${NC}"
code --install-extension ms-vscode.vscode-typescript-next || true
code --install-extension bradlc.vscode-tailwindcss || true
code --install-extension ms-python.python || true
code --install-extension amazonwebservices.aws-toolkit-vscode || true

# Create welcome message
cat > /tmp/codespaces-welcome.txt << EOF
🌀 Welcome to the Echoes Development Environment!

This Codespace includes:
✅ Node.js 18 with npm
✅ Python 3.11 with development tools
✅ AWS CLI and CDK
✅ SAM CLI for serverless development
✅ Docker and Docker Compose
✅ Expo CLI for React Native
✅ LocalStack for AWS services simulation
✅ Pre-configured VS Code extensions

Quick Start:
1. Run 'start-local' to start all development services
2. Run 'serve' to start the frontend development server
3. Open http://localhost:3000 to see your app
4. Use 'awslocal' for AWS CLI commands against LocalStack

Useful URLs:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- DynamoDB Admin: http://localhost:8001
- MailHog: http://localhost:8025
- LocalStack Health: http://localhost:4566/_localstack/health

Documentation: Check the docs/ folder for detailed guides.
EOF

echo -e "${GREEN}"
echo "================================================================="
echo "🎉 Echoes development environment setup complete!"
echo "================================================================="
echo -e "${NC}"

cat /tmp/codespaces-welcome.txt
rm /tmp/codespaces-welcome.txt

echo -e "${YELLOW}💡 Restart your terminal to enable all aliases and configurations.${NC}"
echo -e "${BLUE}🚀 Run 'start-local' to begin development!${NC}"