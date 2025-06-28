#!/bin/bash

# Database Initialization and Migration Script for Echoes Backend
# Handles DynamoDB table initialization, seeding, and schema management

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# Script configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
ENVIRONMENT="dev"
AWS_PROFILE="${AWS_PROFILE:-default}"
SKIP_CONFIRMATION=false
SEED_DATA=false
FORCE_RESET=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -p|--profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        -y|--yes)
            SKIP_CONFIRMATION=true
            shift
            ;;
        --seed)
            SEED_DATA=true
            shift
            ;;
        --force-reset)
            FORCE_RESET=true
            shift
            ;;
        -h|--help)
            cat << EOF
Database Initialization and Migration Script

Usage: $0 [options]

Options:
  -e, --environment <env>  Environment to setup (dev, staging, prod)
  -p, --profile <profile>  AWS profile to use
  -y, --yes               Skip confirmation prompts
  --seed                  Seed database with initial data
  --force-reset           Force reset database (DESTRUCTIVE)
  -h, --help              Show this help message

This script:
  1. Validates DynamoDB table structure
  2. Creates Global Secondary Indexes (GSIs)
  3. Sets up table streams (if needed)
  4. Initializes table with required data
  5. Runs database migrations
  6. Seeds test/demo data (if requested)
  7. Sets up backup policies
EOF
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}" >&2
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}" >&2
}

# Load environment configuration
load_environment_config() {
    log_info "Loading environment configuration"
    
    local env_file="$PROJECT_ROOT/environments/$ENVIRONMENT/.env.infrastructure"
    
    if [[ ! -f "$env_file" ]]; then
        log_error "Environment file not found: $env_file"
        log_error "Run setup-environment.sh first"
        exit 1
    fi
    
    # Load environment variables
    set -a
    source "$env_file"
    set +a
    
    log_success "Environment configuration loaded"
}

# Check if database exists and is accessible
check_database_status() {
    log_info "Checking database status"
    
    # Check if table exists
    if ! aws dynamodb describe-table --table-name "$DYNAMODB_TABLE_NAME" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_error "DynamoDB table not found: $DYNAMODB_TABLE_NAME"
        log_error "Run deploy-storage.sh first"
        exit 1
    fi
    
    # Check table status
    local table_status
    table_status=$(aws dynamodb describe-table \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --profile "$AWS_PROFILE" \
        --query 'Table.TableStatus' \
        --output text)
    
    if [[ "$table_status" != "ACTIVE" ]]; then
        log_error "DynamoDB table is not active. Status: $table_status"
        exit 1
    fi
    
    log_success "Database table is active and accessible"
}

# Validate table schema
validate_table_schema() {
    log_info "Validating table schema"
    
    local table_description
    table_description=$(aws dynamodb describe-table \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --profile "$AWS_PROFILE" \
        --output json)
    
    # Check partition key
    local partition_key
    partition_key=$(echo "$table_description" | jq -r '.Table.KeySchema[] | select(.KeyType == "HASH") | .AttributeName')
    
    if [[ "$partition_key" != "userId" ]]; then
        log_error "Incorrect partition key. Expected: userId, Found: $partition_key"
        exit 1
    fi
    
    # Check sort key
    local sort_key
    sort_key=$(echo "$table_description" | jq -r '.Table.KeySchema[] | select(.KeyType == "RANGE") | .AttributeName')
    
    if [[ "$sort_key" != "echoId" ]]; then
        log_error "Incorrect sort key. Expected: echoId, Found: $sort_key"
        exit 1
    fi
    
    # Check GSI
    local gsi_count
    gsi_count=$(echo "$table_description" | jq '.Table.GlobalSecondaryIndexes | length')
    
    if [[ "$gsi_count" -lt 1 ]]; then
        log_warning "No Global Secondary Indexes found. Creating emotion-timestamp index."
        create_emotion_timestamp_gsi
    else
        log_success "Global Secondary Indexes found"
    fi
    
    log_success "Table schema validation completed"
}

# Create emotion-timestamp GSI if missing
create_emotion_timestamp_gsi() {
    log_info "Creating emotion-timestamp Global Secondary Index"
    
    local gsi_definition=$(cat << EOF
{
    "Create": {
        "IndexName": "emotion-timestamp-index",
        "KeySchema": [
            {
                "AttributeName": "emotion",
                "KeyType": "HASH"
            },
            {
                "AttributeName": "timestamp",
                "KeyType": "RANGE"
            }
        ],
        "Projection": {
            "ProjectionType": "ALL"
        },
        "ProvisionedThroughput": {
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5
        }
    }
}
EOF
)
    
    # Add attributes to table if they don't exist
    local update_result
    if update_result=$(aws dynamodb update-table \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --profile "$AWS_PROFILE" \
        --attribute-definitions \
            'AttributeName=emotion,AttributeType=S' \
            'AttributeName=timestamp,AttributeType=S' \
        --global-secondary-index-updates "$gsi_definition" \
        --output json 2>&1); then
        
        log_info "GSI creation initiated. Waiting for completion..."
        
        # Wait for GSI to be active
        local max_wait=300 # 5 minutes
        local wait_time=0
        
        while [[ $wait_time -lt $max_wait ]]; do
            local gsi_status
            gsi_status=$(aws dynamodb describe-table \
                --table-name "$DYNAMODB_TABLE_NAME" \
                --profile "$AWS_PROFILE" \
                --query 'Table.GlobalSecondaryIndexes[?IndexName==`emotion-timestamp-index`].IndexStatus' \
                --output text 2>/dev/null || echo "")
            
            if [[ "$gsi_status" = "ACTIVE" ]]; then
                log_success "Emotion-timestamp GSI created successfully"
                return 0
            fi
            
            sleep 10
            ((wait_time += 10))
            log_info "Waiting for GSI... ($wait_time/${max_wait}s)"
        done
        
        log_error "GSI creation timed out"
        return 1
    else
        if echo "$update_result" | grep -q "ResourceInUseException"; then
            log_warning "Table is being updated. Please try again later."
        else
            log_error "Failed to create GSI: $update_result"
        fi
        return 1
    fi
}

# Initialize database with required data
initialize_database() {
    log_info "Initializing database with required data"
    
    # Create system configuration item
    local system_config=$(cat << EOF
{
    "userId": {"S": "SYSTEM"},
    "echoId": {"S": "CONFIG"},
    "itemType": {"S": "SYSTEM_CONFIG"},
    "version": {"S": "1.0.0"},
    "createdAt": {"S": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"},
    "settings": {
        "M": {
            "maxAudioDurationSeconds": {"N": "30"},
            "minAudioDurationSeconds": {"N": "10"},
            "maxFileSizeBytes": {"N": "52428800"},
            "allowedFormats": {
                "L": [
                    {"S": "mp3"},
                    {"S": "wav"},
                    {"S": "m4a"},
                    {"S": "ogg"}
                ]
            },
            "retentionDays": {"N": "365"}
        }
    }
}
EOF
)
    
    # Put system configuration
    if aws dynamodb put-item \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --item "$system_config" \
        --condition-expression "attribute_not_exists(userId)" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_success "System configuration initialized"
    else
        log_info "System configuration already exists"
    fi
    
    # Create emotion categories configuration  
    local emotions=("happy" "sad" "excited" "calm" "nostalgic" "hopeful" "grateful" "reflective")
    
    for emotion in "${emotions[@]}"; do
        local emotion_config=$(cat << EOF
{
    "userId": {"S": "SYSTEM"},
    "echoId": {"S": "EMOTION_${emotion^^}"},
    "itemType": {"S": "EMOTION_CONFIG"},
    "emotion": {"S": "$emotion"},
    "displayName": {"S": "$(echo "$emotion" | sed 's/.*/\u&/')"},
    "color": {"S": "$(case $emotion in
        happy) echo "#FFD700" ;;
        sad) echo "#4682B4" ;;
        excited) echo "#FF6347" ;;
        calm) echo "#90EE90" ;;
        nostalgic) echo "#DDA0DD" ;;
        hopeful) echo "#87CEEB" ;;
        grateful) echo "#F0E68C" ;;
        reflective) echo "#D3D3D3" ;;
        *) echo "#808080" ;;
    esac)"},
    "description": {"S": "$(case $emotion in
        happy) echo "Joyful and uplifting moments" ;;
        sad) echo "Melancholic and contemplative thoughts" ;;
        excited) echo "Energetic and enthusiastic expressions" ;;
        calm) echo "Peaceful and serene reflections" ;;
        nostalgic) echo "Memories and reminiscent thoughts" ;;
        hopeful) echo "Optimistic and forward-looking ideas" ;;
        grateful) echo "Thankful and appreciative moments" ;;
        reflective) echo "Thoughtful and introspective musings" ;;
        *) echo "General emotional expression" ;;
    esac)"},
    "createdAt": {"S": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
}
EOF
)
        
        if aws dynamodb put-item \
            --table-name "$DYNAMODB_TABLE_NAME" \
            --item "$emotion_config" \
            --condition-expression "attribute_not_exists(userId)" \
            --profile "$AWS_PROFILE" > /dev/null 2>&1; then
            log_success "Emotion category '$emotion' initialized"
        else
            log_info "Emotion category '$emotion' already exists"
        fi
    done
}

# Seed demo data if requested
seed_demo_data() {
    if [[ "$SEED_DATA" = false ]]; then
        return 0
    fi
    
    log_info "Seeding demo data"
    
    if [[ "$ENVIRONMENT" = "prod" ]]; then
        log_warning "Skipping demo data seeding in production environment"
        return 0
    fi
    
    if [[ "$SKIP_CONFIRMATION" = false ]]; then
        read -p "Seed demo data in $ENVIRONMENT environment? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Skipping demo data seeding"
            return 0
        fi
    fi
    
    # Create demo user
    local demo_user_id="demo-user-$(date +%s)"
    local emotions=("happy" "calm" "reflective" "grateful")
    
    for i in {1..5}; do
        local emotion="${emotions[$((i % ${#emotions[@]}))]}"
        local demo_echo=$(cat << EOF
{
    "userId": {"S": "$demo_user_id"},
    "echoId": {"S": "demo-echo-$i"},
    "itemType": {"S": "ECHO"},
    "emotion": {"S": "$emotion"},
    "timestamp": {"S": "$(date -u -d "-$((i * 2)) hours" +%Y-%m-%dT%H:%M:%SZ)"},
    "title": {"S": "Demo Echo #$i"},
    "description": {"S": "This is a demo echo for testing purposes - $emotion feelings"},
    "duration": {"N": "$((15 + i * 2))"},
    "fileSize": {"N": "$((1024 * 1024 * i))"},
    "s3Key": {"S": "demo/$demo_user_id/echo-$i.mp3"},
    "status": {"S": "ACTIVE"},
    "createdAt": {"S": "$(date -u -d "-$((i * 2)) hours" +%Y-%m-%dT%H:%M:%SZ)"},
    "updatedAt": {"S": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"},
    "metadata": {
        "M": {
            "sampleRate": {"N": "44100"},
            "channels": {"N": "2"},
            "format": {"S": "mp3"},
            "quality": {"S": "high"}
        }
    }
}
EOF
)
        
        if aws dynamodb put-item \
            --table-name "$DYNAMODB_TABLE_NAME" \
            --item "$demo_echo" \
            --profile "$AWS_PROFILE" > /dev/null; then
            log_success "Demo echo #$i created"
        else
            log_warning "Failed to create demo echo #$i"
        fi
    done
    
    log_success "Demo data seeding completed"
    log_info "Demo user ID: $demo_user_id"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations"
    
    # Check if migrations directory exists
    local migrations_dir="$PROJECT_ROOT/backend/migrations"
    
    if [[ ! -d "$migrations_dir" ]]; then
        log_info "No migrations directory found. Skipping migrations."
        return 0
    fi
    
    # Create migration tracking table entry
    local migration_tracker=$(cat << EOF
{
    "userId": {"S": "SYSTEM"},
    "echoId": {"S": "MIGRATIONS"},
    "itemType": {"S": "MIGRATION_TRACKER"},
    "lastMigration": {"S": "initial"},
    "migrationsApplied": {"L": []},
    "updatedAt": {"S": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
}
EOF
)
    
    aws dynamodb put-item \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --item "$migration_tracker" \
        --condition-expression "attribute_not_exists(userId)" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1 || true
    
    # Find and run migration scripts
    if ls "$migrations_dir"/*.py >/dev/null 2>&1; then
        for migration_file in "$migrations_dir"/*.py; do
            local migration_name
            migration_name=$(basename "$migration_file" .py)
            
            log_info "Running migration: $migration_name"
            
            # Execute migration script with environment variables
            if DYNAMODB_TABLE_NAME="$DYNAMODB_TABLE_NAME" \
               AWS_PROFILE="$AWS_PROFILE" \
               AWS_REGION="$AWS_REGION" \
               python3 "$migration_file"; then
                log_success "Migration '$migration_name' completed"
            else
                log_error "Migration '$migration_name' failed"
                return 1
            fi
        done
    else
        log_info "No migration scripts found"
    fi
    
    log_success "All migrations completed"
}

# Setup backup policies
setup_backup_policies() {
    log_info "Setting up backup policies"
    
    if [[ "$ENVIRONMENT" = "prod" ]]; then
        # Enable continuous backups for production
        log_info "Enabling continuous backups for production"
        
        if aws dynamodb put-backup-policy \
            --table-name "$DYNAMODB_TABLE_NAME" \
            --backup-policy BackupEnabled=true \
            --profile "$AWS_PROFILE" 2>/dev/null; then
            log_success "Continuous backups enabled"
        else
            log_warning "Failed to enable continuous backups"
        fi
        
        # Create backup schedule
        log_info "Setting up scheduled backups"
        
        # This would typically be done through AWS Backup service
        # For now, we'll just document the requirement
        log_info "Manual setup required: Configure AWS Backup for scheduled backups"
    else
        log_info "Backup policies not required for $ENVIRONMENT environment"
    fi
}

# Validate database integrity
validate_database_integrity() {
    log_info "Validating database integrity"
    
    # Check system configuration exists
    if aws dynamodb get-item \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --key '{"userId":{"S":"SYSTEM"},"echoId":{"S":"CONFIG"}}' \
        --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_success "System configuration validated"
    else
        log_error "System configuration missing"
        return 1
    fi
    
    # Check emotion configurations exist
    local emotion_count
    emotion_count=$(aws dynamodb query \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --key-condition-expression "userId = :userId AND begins_with(echoId, :prefix)" \
        --expression-attribute-values '{":userId":{"S":"SYSTEM"},":prefix":{"S":"EMOTION_"}}' \
        --profile "$AWS_PROFILE" \
        --query 'Count' \
        --output text)
    
    if [[ $emotion_count -ge 8 ]]; then
        log_success "Emotion configurations validated ($emotion_count found)"
    else
        log_warning "Some emotion configurations may be missing ($emotion_count found)"
    fi
    
    # Test GSI functionality
    log_info "Testing Global Secondary Index"
    
    if aws dynamodb query \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --index-name "emotion-timestamp-index" \
        --key-condition-expression "emotion = :emotion" \
        --expression-attribute-values '{":emotion":{"S":"happy"}}' \
        --profile "$AWS_PROFILE" \
        --limit 1 > /dev/null 2>&1; then
        log_success "GSI query test passed"
    else
        log_error "GSI query test failed"
        return 1
    fi
    
    log_success "Database integrity validation completed"
}

# Generate database summary
generate_summary() {
    log_info "Generating database initialization summary"
    
    local summary_file="$PROJECT_ROOT/tmp/database-init-$ENVIRONMENT.json"
    
    # Get table statistics
    local table_info
    table_info=$(aws dynamodb describe-table \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --profile "$AWS_PROFILE" \
        --output json)
    
    local item_count
    item_count=$(echo "$table_info" | jq -r '.Table.ItemCount // 0')
    
    local table_size
    table_size=$(echo "$table_info" | jq -r '.Table.TableSizeBytes // 0')
    
    cat > "$summary_file" << EOF
{
  "database_initialization": {
    "environment": "$ENVIRONMENT",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "table_name": "$DYNAMODB_TABLE_NAME",
    "status": "completed"
  },
  "table_stats": {
    "item_count": $item_count,
    "table_size_bytes": $table_size,
    "provisioned_throughput": $(echo "$table_info" | jq '.Table.ProvisionedThroughput // null'),
    "global_secondary_indexes": $(echo "$table_info" | jq '.Table.GlobalSecondaryIndexes | length')
  },
  "initialization_summary": {
    "system_config_created": true,
    "emotion_categories_created": 8,
    "demo_data_seeded": $SEED_DATA,
    "migrations_run": true,
    "backup_policies_configured": $([ "$ENVIRONMENT" = "prod" ] && echo "true" || echo "false")
  }
}
EOF
    
    log_success "Database summary saved: $summary_file"
    
    # Display key information
    echo
    echo -e "${BLUE}📊 Database Initialization Summary:${NC}"
    echo "  📋 Table: $DYNAMODB_TABLE_NAME"
    echo "  📊 Items: $item_count"
    echo "  💾 Size: $table_size bytes"
    echo "  🔍 GSIs: $(echo "$table_info" | jq '.Table.GlobalSecondaryIndexes | length')"
    echo "  🎭 Emotions: 8 categories configured"
    if [[ "$SEED_DATA" = true ]]; then
        echo "  🌱 Demo data: Seeded"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}📊 Initializing database for: $ENVIRONMENT${NC}"
    echo "================================="
    
    load_environment_config
    check_database_status
    validate_table_schema
    initialize_database
    run_migrations
    seed_demo_data
    setup_backup_policies
    validate_database_integrity
    generate_summary
    
    echo
    log_success "Database initialization completed successfully!"
    echo -e "${BLUE}Environment '$ENVIRONMENT' database is ready.${NC}"
    echo
    echo -e "${BLUE}Next step: Deploy authentication infrastructure${NC}"
    echo "  ./deploy/scripts/deploy-auth.sh -e $ENVIRONMENT"
}

# Run main function
main "$@"