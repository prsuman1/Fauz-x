#!/usr/bin/env bash
# migrate_to_testing.sh — Deploy FaujX app to a testing environment
# Run from project root on Mac: ./migrate_to_testing.sh
set -euo pipefail

# =============================================================================
# FILL IN THESE VARIABLES BEFORE RUNNING
# =============================================================================

# Test EC2
TEST_EC2_IP="FILL_ME"
TEST_EC2_USER="ubuntu"
TEST_EC2_KEY="FILL_ME"           # SSH key path, e.g. ./test-aws.pem

# Test RDS
TEST_RDS_HOST="FILL_ME"
TEST_RDS_PORT="5432"
TEST_RDS_USER="FILL_ME"
TEST_RDS_PASSWORD="FILL_ME"

# Database names (defaults match dev)
TEST_DB_NAME="faujx_dev"
TEST_MCQ_DB_NAME="mcq_database"

# =============================================================================
# LOCAL TOOL PATHS (Homebrew PG 17)
# =============================================================================
PG_RESTORE="/opt/homebrew/bin/pg_restore-17"
PSQL="/opt/homebrew/bin/psql-17"

# =============================================================================
# PATHS
# =============================================================================
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DUMP_FILE="${PROJECT_DIR}/FaujXDev Dump"
MCQ_SCHEMA="${PROJECT_DIR}/app/db/mcq_full_schema.sql"
ENV_FILE="${PROJECT_DIR}/.env"
ENV_TEST="${PROJECT_DIR}/.env.test"
REMOTE_DIR="/home/${TEST_EC2_USER}/Fauz-x"

# Validate prerequisites
for f in "$DUMP_FILE" "$MCQ_SCHEMA" "$ENV_FILE"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: Required file not found: $f"
        exit 1
    fi
done
for tool in "$PG_RESTORE" "$PSQL"; do
    if [[ ! -x "$tool" ]]; then
        echo "ERROR: Tool not found or not executable: $tool"
        exit 1
    fi
done
if [[ "$TEST_EC2_IP" == "FILL_ME" || "$TEST_RDS_HOST" == "FILL_ME" ]]; then
    echo "ERROR: Please fill in the placeholder variables at the top of this script."
    exit 1
fi

SSH_CMD="ssh -i ${TEST_EC2_KEY} -o StrictHostKeyChecking=no ${TEST_EC2_USER}@${TEST_EC2_IP}"

echo "============================================"
echo "FaujX Migration to Testing Environment"
echo "============================================"
echo "Test EC2:  ${TEST_EC2_USER}@${TEST_EC2_IP}"
echo "Test RDS:  ${TEST_RDS_HOST}:${TEST_RDS_PORT}"
echo "Databases: ${TEST_DB_NAME}, ${TEST_MCQ_DB_NAME}"
echo ""

# ─────────────────────────────────────────────────────────────
# Step 1: Restore faujx_dev to test RDS
# ─────────────────────────────────────────────────────────────
echo ">>> Step 1: Restoring ${TEST_DB_NAME} from pg_dump..."
PGPASSWORD="$TEST_RDS_PASSWORD" "$PG_RESTORE" \
    --host="$TEST_RDS_HOST" \
    --port="$TEST_RDS_PORT" \
    --username="$TEST_RDS_USER" \
    --dbname="$TEST_DB_NAME" \
    --clean --if-exists \
    --no-owner --no-privileges \
    "$DUMP_FILE" || {
        echo "WARNING: pg_restore exited with warnings (this is normal for --clean --if-exists on first run)"
    }
echo "    Done: ${TEST_DB_NAME} restored."
echo ""

# ─────────────────────────────────────────────────────────────
# Step 2: Create MCQ database tables
# ─────────────────────────────────────────────────────────────
echo ">>> Step 2: Creating MCQ tables in ${TEST_MCQ_DB_NAME}..."
PGPASSWORD="$TEST_RDS_PASSWORD" "$PSQL" \
    --host="$TEST_RDS_HOST" \
    --port="$TEST_RDS_PORT" \
    --username="$TEST_RDS_USER" \
    --dbname="$TEST_MCQ_DB_NAME" \
    -f "$MCQ_SCHEMA"
echo "    Done: MCQ tables created."
echo ""

# ─────────────────────────────────────────────────────────────
# Step 3: Generate .env.test
# ─────────────────────────────────────────────────────────────
echo ">>> Step 3: Generating .env.test..."
cp "$ENV_FILE" "$ENV_TEST"

# Replace DB credentials
sed -i '' "s|^DATABASE_HOST=.*|DATABASE_HOST=${TEST_RDS_HOST}|" "$ENV_TEST"
sed -i '' "s|^DATABASE_PORT=.*|DATABASE_PORT=${TEST_RDS_PORT}|" "$ENV_TEST"
sed -i '' "s|^DATABASE_NAME=.*|DATABASE_NAME=${TEST_DB_NAME}|" "$ENV_TEST"
sed -i '' "s|^DATABASE_USER=.*|DATABASE_USER=${TEST_RDS_USER}|" "$ENV_TEST"
sed -i '' "s|^DATABASE_PASSWORD=.*|DATABASE_PASSWORD=${TEST_RDS_PASSWORD}|" "$ENV_TEST"
sed -i '' "s|^MCQ_DATABASE_HOST=.*|MCQ_DATABASE_HOST=${TEST_RDS_HOST}|" "$ENV_TEST"
sed -i '' "s|^MCQ_DATABASE_PORT=.*|MCQ_DATABASE_PORT=${TEST_RDS_PORT}|" "$ENV_TEST"
sed -i '' "s|^MCQ_DATABASE_NAME=.*|MCQ_DATABASE_NAME=${TEST_MCQ_DB_NAME}|" "$ENV_TEST"
sed -i '' "s|^MCQ_DATABASE_USER=.*|MCQ_DATABASE_USER=${TEST_RDS_USER}|" "$ENV_TEST"
sed -i '' "s|^MCQ_DATABASE_PASSWORD=.*|MCQ_DATABASE_PASSWORD=${TEST_RDS_PASSWORD}|" "$ENV_TEST"

# Set environment
sed -i '' "s|^APP_ENV=.*|APP_ENV=testing|" "$ENV_TEST"

# Update server info
sed -i '' "s|^IP.*=.*|IP=${TEST_EC2_IP}|" "$ENV_TEST"

echo "    Done: .env.test generated at ${ENV_TEST}"
echo ""

# ─────────────────────────────────────────────────────────────
# Step 4: Deploy code to test EC2
# ─────────────────────────────────────────────────────────────
echo ">>> Step 4: Deploying code to test EC2..."
rsync -avz --delete \
    -e "ssh -i ${TEST_EC2_KEY} -o StrictHostKeyChecking=no" \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='FaujXDev Dump' \
    --exclude='.env' \
    --exclude='.env.test' \
    --exclude='*.pem' \
    --exclude='load_test_results.csv' \
    "${PROJECT_DIR}/" "${TEST_EC2_USER}@${TEST_EC2_IP}:${REMOTE_DIR}/"

echo "    Uploading .env.test as .env on remote..."
scp -i "${TEST_EC2_KEY}" -o StrictHostKeyChecking=no \
    "$ENV_TEST" "${TEST_EC2_USER}@${TEST_EC2_IP}:${REMOTE_DIR}/.env"

echo "    Done: Code deployed."
echo ""

# ─────────────────────────────────────────────────────────────
# Step 5: Remote setup on test EC2
# ─────────────────────────────────────────────────────────────
echo ">>> Step 5: Setting up and starting server on test EC2..."
$SSH_CMD << 'REMOTE_SCRIPT'
set -euo pipefail
cd ~/Fauz-x

# Create virtualenv if not exists
if [ ! -d "venv" ]; then
    echo "    Creating virtualenv..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "    Installing dependencies..."
pip install -r requirements.txt --quiet

# Kill existing uvicorn (may kill SSH — that's OK, server still starts)
echo "    Stopping any existing server..."
pkill -f uvicorn || true
sleep 1

echo "    Starting server..."
nohup python3 -c 'import uvicorn; uvicorn.run("app.main:app", host="0.0.0.0", port=8000)' > /tmp/faujx.log 2>&1 &
echo "    Server PID: $!"

sleep 3

echo "    Checking health..."
curl -sf http://localhost:8000/api/health && echo "" || echo "WARNING: Health check failed — check /tmp/faujx.log on the server"
REMOTE_SCRIPT

echo ""
echo "============================================"
echo "Migration complete!"
echo "============================================"
echo ""
echo "Verify from your Mac:"
echo "  curl http://${TEST_EC2_IP}:8000/api/health"
echo ""
echo "Check server logs:"
echo "  ${SSH_CMD} 'tail -50 /tmp/faujx.log'"
echo ""
