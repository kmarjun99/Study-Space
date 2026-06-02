#!/usr/bin/env bash
# =============================================================================
# deploy-gcp.sh — First-time GCP setup & deploy for Study Space
#
# Usage (from repo root):
#   chmod +x deploy-gcp.sh && ./deploy-gcp.sh
#
# What this does:
#   1. Creates / selects a GCP project
#   2. Enables required APIs
#   3. Creates Artifact Registry repo
#   4. Creates Cloud SQL PostgreSQL instance + DB + user
#   5. Stores secrets in Secret Manager (only non-empty ones)
#   6. Builds and pushes Docker images
#   7. Deploys backend  → Cloud Run
#   8. Deploys frontend → Cloud Run  (backend URL baked in at build time)
#   9. Prints live URLs + CI/CD instructions
#
# Prerequisites:
#   - gcloud CLI installed + logged in  (gcloud auth login)
#   - Docker installed and running
# =============================================================================
set -euo pipefail

# ─── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
success() { echo -e "${GREEN}[ OK ]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET} $*"; }
die()     { echo -e "${RED}[ERR ]${RESET} $*" >&2; exit 1; }

# ─── Prompt helpers ───────────────────────────────────────────────────────────
# Required value (errors if empty and no default)
prompt() {
  local var=$1 question=$2 default="${3:-}"
  local hint=""; [[ -n "$default" ]] && hint=" [${default}]"
  read -rp "$(echo -e "${BOLD}${question}${hint}: ${RESET}")" _val
  _val="${_val:-$default}"
  [[ -z "$_val" ]] && die "A value is required for: $question"
  printf -v "$var" '%s' "$_val"
}

# Optional value (empty is fine)
prompt_opt() {
  local var=$1 question=$2 default="${3:-}"
  local hint=""
  [[ -n "$default" ]] && hint=" [${default}]"
  [[ -z "$default" ]] && hint=" (press Enter to skip)"
  read -rp "$(echo -e "${BOLD}${question}${hint}: ${RESET}")" _val
  _val="${_val:-$default}"
  printf -v "$var" '%s' "$_val"
}

# Required hidden input (for passwords)
prompt_pass() {
  local var=$1 question=$2
  read -rsp "$(echo -e "${BOLD}${question}: ${RESET}")" _val; echo
  [[ -z "$_val" ]] && die "A value is required for: $question"
  printf -v "$var" '%s' "$_val"
}

# Optional hidden input
prompt_pass_opt() {
  local var=$1 question=$2
  read -rsp "$(echo -e "${BOLD}${question} (press Enter to skip): ${RESET}")" _val; echo
  printf -v "$var" '%s' "$_val"
}

# ─── Secret helpers ───────────────────────────────────────────────────────────
secret_exists() { gcloud secrets describe "$1" --project="$PROJECT_ID" &>/dev/null; }

upsert_secret() {
  local name=$1 value=$2
  if [[ -z "$value" ]]; then
    info "Skipping secret $name (no value provided)"
    return
  fi
  if secret_exists "$name"; then
    echo -n "$value" | gcloud secrets versions add "$name" --data-file=- --project="$PROJECT_ID" &>/dev/null
    info "Secret $name updated"
  else
    echo -n "$value" | gcloud secrets create "$name" --data-file=- --replication-policy=automatic --project="$PROJECT_ID" &>/dev/null
    success "Secret $name created"
  fi
}

# Build a --set-secrets flag value only for secrets that exist in Secret Manager
build_secret_flags() {
  local flags=""
  local pairs=(
    "DATABASE_URL=DATABASE_URL"
    "SECRET_KEY=SECRET_KEY"
    "mail_username=MAIL_USERNAME"
    "mail_password=MAIL_PASSWORD"
    "SENDGRID_API_KEY=SENDGRID_API_KEY"
    "RAZORPAY_KEY_ID=RAZORPAY_KEY_ID"
    "RAZORPAY_KEY_SECRET=RAZORPAY_KEY_SECRET"
  )
  for pair in "${pairs[@]}"; do
    local env_name="${pair%%=*}"
    local secret_name="${pair##*=}"
    if secret_exists "$secret_name"; then
      [[ -n "$flags" ]] && flags+=","
      flags+="${env_name}=${secret_name}:latest"
    fi
  done
  echo "$flags"
}

# ─────────────────────────────────────────────────────────────────────────────
# 0. Collect all configuration upfront
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║    Study Space  ·  GCP First-Time Deploy   ║${RESET}"
echo -e "${BOLD}╚════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "${CYAN}Required fields are marked *, everything else can be skipped.${RESET}"
echo ""

# Required
prompt    PROJECT_ID  "* GCP Project ID"        "study-space-prod"
prompt    REGION      "* GCP Region"             "asia-south1"
prompt_pass DB_PASSWORD "* PostgreSQL password (make up a strong one)"

# OTP / Email — Gmail SMTP (free, no extra account needed)
echo ""
echo -e "${BOLD}─── OTP / Email (Gmail SMTP) ────────────────────────────────────────${RESET}"
echo -e "  Use your Gmail to send OTP emails. You need a Gmail App Password."
echo -e "  How to get one: ${CYAN}https://myaccount.google.com/apppasswords${RESET}"
echo -e "  (Enable 2FA on your Google account first, then create an App Password)"
echo ""
prompt_opt  MAIL_USER  "* Gmail address for sending OTPs" "kmarjun99@gmail.com"
prompt_pass_opt MAIL_PASS "* Gmail App Password (16-char code)"

# Payments — can add later
echo ""
echo -e "${BOLD}─── Payments (Razorpay) — add later if not ready ───────────────────${RESET}"
prompt_opt  RAZORPAY_ID  "Razorpay Key ID"
prompt_opt  RAZORPAY_SEC "Razorpay Key Secret"

# SendGrid — optional, Gmail above handles OTP
echo ""
echo -e "${BOLD}─── SendGrid (optional — Gmail above is enough for OTP) ────────────${RESET}"
prompt_opt  SENDGRID_KEY "SendGrid API key"

# Frontend keys
echo ""
echo -e "${BOLD}─── Frontend API keys ───────────────────────────────────────────────${RESET}"
prompt_opt  MAPS_KEY    "Google Maps API key"
prompt_opt  GEMINI_KEY  "Gemini API key (for AI features)"

# Custom domain
echo ""
prompt_opt  CUSTOM_DOMAIN "Custom domain for frontend (e.g. studyspaceapp.in)"

# ─── Derived values ───────────────────────────────────────────────────────────
REPO_NAME="study-space"
SQL_INSTANCE="study-space-db"
DB_NAME="studyspace"
DB_USER="appuser"
BACKEND_SVC="study-space-backend"
FRONTEND_SVC="study-space-frontend"
IMAGE_PREFIX="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
DEMO_MODE="false"; [[ -z "$RAZORPAY_ID" ]] && DEMO_MODE="true"

echo ""
echo -e "${BOLD}─────────────────────────────────────────────────────────────────────${RESET}"
info "Project       : $PROJECT_ID"
info "Region        : $REGION"
info "Payment mode  : $([ "$DEMO_MODE" = "true" ] && echo "DEMO (no real charges)" || echo "LIVE")"
info "Email via     : $([ -n "$MAIL_USER" ] && echo "Gmail SMTP ($MAIL_USER)" || echo "Disabled")"
echo -e "${BOLD}─────────────────────────────────────────────────────────────────────${RESET}"
echo ""
read -rp "$(echo -e "${BOLD}Looks good? Press Enter to start deploying, or Ctrl+C to cancel: ${RESET}")"

# ─────────────────────────────────────────────────────────────────────────────
# 1. GCP Project
# ─────────────────────────────────────────────────────────────────────────────
info "Setting up GCP project..."
if gcloud projects describe "$PROJECT_ID" &>/dev/null; then
  info "Project '$PROJECT_ID' already exists — reusing."
else
  gcloud projects create "$PROJECT_ID" --name="Study Space" || \
    die "Failed to create project. If it already exists with a different owner, choose a different Project ID."
  success "Project '$PROJECT_ID' created."
  echo ""
  warn "ACTION NEEDED: Link a billing account before continuing."
  warn "Open: https://console.cloud.google.com/billing/linkedaccount?project=${PROJECT_ID}"
  warn "Then press Enter here to continue."
  read -rp ""
fi
gcloud config set project "$PROJECT_ID" --quiet

# ─────────────────────────────────────────────────────────────────────────────
# 2. Enable APIs
# ─────────────────────────────────────────────────────────────────────────────
info "Enabling GCP APIs (may take 1–2 min on first run)..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  --project="$PROJECT_ID" --quiet
success "APIs enabled."

# ─────────────────────────────────────────────────────────────────────────────
# 3. Artifact Registry
# ─────────────────────────────────────────────────────────────────────────────
info "Setting up Artifact Registry..."
if gcloud artifacts repositories describe "$REPO_NAME" \
    --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
  info "Repository '$REPO_NAME' already exists."
else
  gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --project="$PROJECT_ID"
  success "Repository created."
fi
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
success "Docker auth configured for Artifact Registry."

# ─────────────────────────────────────────────────────────────────────────────
# 4. Cloud SQL (PostgreSQL)
# ─────────────────────────────────────────────────────────────────────────────
info "Provisioning Cloud SQL PostgreSQL instance (5–10 min on first run)..."
if gcloud sql instances describe "$SQL_INSTANCE" --project="$PROJECT_ID" &>/dev/null; then
  info "SQL instance '$SQL_INSTANCE' already exists."
else
  gcloud sql instances create "$SQL_INSTANCE" \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region="$REGION" \
    --storage-type=SSD \
    --storage-size=10GB \
    --project="$PROJECT_ID"
  success "SQL instance created."
fi

info "Creating database '$DB_NAME' and user '$DB_USER'..."
gcloud sql databases create "$DB_NAME" --instance="$SQL_INSTANCE" \
  --project="$PROJECT_ID" 2>/dev/null || info "Database already exists."
gcloud sql users create "$DB_USER" --instance="$SQL_INSTANCE" \
  --password="$DB_PASSWORD" --project="$PROJECT_ID" 2>/dev/null || \
  gcloud sql users set-password "$DB_USER" --instance="$SQL_INSTANCE" \
    --password="$DB_PASSWORD" --project="$PROJECT_ID"
success "Database and user ready."

CLOUDSQL_INSTANCE="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"
DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${CLOUDSQL_INSTANCE}"

# ─────────────────────────────────────────────────────────────────────────────
# 5. Secret Manager
# ─────────────────────────────────────────────────────────────────────────────
info "Storing secrets in Secret Manager (skipping any that are blank)..."
upsert_secret "DATABASE_URL"        "$DATABASE_URL"
upsert_secret "SECRET_KEY"          "$SECRET_KEY"
upsert_secret "MAIL_USERNAME"       "$MAIL_USER"
upsert_secret "MAIL_PASSWORD"       "$MAIL_PASS"
upsert_secret "SENDGRID_API_KEY"    "$SENDGRID_KEY"
upsert_secret "RAZORPAY_KEY_ID"     "$RAZORPAY_ID"
upsert_secret "RAZORPAY_KEY_SECRET" "$RAZORPAY_SEC"
success "Secrets stored."

# Grant Cloud Run compute SA access to Secret Manager
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
CLOUD_RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
info "Granting Cloud Run service account access to secrets..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUD_RUN_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None --quiet 2>/dev/null || true
success "IAM policy set."

# Build secret flags dynamically (only existing secrets)
SECRET_FLAGS=$(build_secret_flags)

# ─────────────────────────────────────────────────────────────────────────────
# 6. Build & push backend image
# ─────────────────────────────────────────────────────────────────────────────
info "Building backend Docker image (linux/amd64 for Cloud Run)..."
docker build --platform linux/amd64 \
  -t "${IMAGE_PREFIX}/backend:latest" \
  -f backend/Dockerfile \
  backend/
docker push "${IMAGE_PREFIX}/backend:latest"
success "Backend image pushed → ${IMAGE_PREFIX}/backend:latest"

# ─────────────────────────────────────────────────────────────────────────────
# 7. Deploy backend → Cloud Run (first pass, to get its URL)
# ─────────────────────────────────────────────────────────────────────────────
info "Deploying backend to Cloud Run..."

DEPLOY_ARGS=(
  run deploy "$BACKEND_SVC"
  --image="${IMAGE_PREFIX}/backend:latest"
  --region="$REGION"
  --platform=managed
  --allow-unauthenticated
  --port=8000
  --memory=512Mi
  --cpu=1
  --min-instances=0
  --max-instances=10
  --add-cloudsql-instances="$CLOUDSQL_INSTANCE"
  --set-env-vars="ENVIRONMENT=production,ALGORITHM=HS256,PAYMENT_DEMO_MODE=${DEMO_MODE},mail_from=${MAIL_USER},mail_server=smtp.gmail.com,mail_port=587"
  --project="$PROJECT_ID"
)
[[ -n "$SECRET_FLAGS" ]] && DEPLOY_ARGS+=(--set-secrets="$SECRET_FLAGS")

gcloud "${DEPLOY_ARGS[@]}"

BACKEND_URL=$(gcloud run services describe "$BACKEND_SVC" \
  --region="$REGION" --project="$PROJECT_ID" \
  --format="value(status.url)")
success "Backend live at: $BACKEND_URL"

# ─────────────────────────────────────────────────────────────────────────────
# 8. Build & push frontend (backend URL baked in)
# ─────────────────────────────────────────────────────────────────────────────
info "Building frontend Docker image (linux/amd64 for Cloud Run, API URL: $BACKEND_URL)..."
docker build --platform linux/amd64 \
  -t "${IMAGE_PREFIX}/frontend:latest" \
  --build-arg "VITE_API_BASE_URL=${BACKEND_URL}" \
  --build-arg "VITE_GOOGLE_MAPS_API_KEY=${MAPS_KEY}" \
  --build-arg "GEMINI_API_KEY=${GEMINI_KEY}" \
  -f frontend/Dockerfile \
  frontend/
docker push "${IMAGE_PREFIX}/frontend:latest"
success "Frontend image pushed → ${IMAGE_PREFIX}/frontend:latest"

# ─────────────────────────────────────────────────────────────────────────────
# 9. Deploy frontend → Cloud Run
# ─────────────────────────────────────────────────────────────────────────────
info "Deploying frontend to Cloud Run..."
gcloud run deploy "$FRONTEND_SVC" \
  --image="${IMAGE_PREFIX}/frontend:latest" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --port=80 \
  --memory=256Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=5 \
  --project="$PROJECT_ID"

FRONTEND_URL=$(gcloud run services describe "$FRONTEND_SVC" \
  --region="$REGION" --project="$PROJECT_ID" \
  --format="value(status.url)")
success "Frontend live at: $FRONTEND_URL"

# Update backend CORS to allow the frontend URL
info "Updating backend CORS to allow frontend URL..."
gcloud run services update "$BACKEND_SVC" \
  --region="$REGION" \
  --update-env-vars="CORS_ORIGINS=${FRONTEND_URL}" \
  --project="$PROJECT_ID" --quiet
success "CORS updated."

# ─────────────────────────────────────────────────────────────────────────────
# 10. Custom domain (optional)
# ─────────────────────────────────────────────────────────────────────────────
if [[ -n "$CUSTOM_DOMAIN" ]]; then
  info "Mapping custom domain '$CUSTOM_DOMAIN' to frontend..."
  gcloud run domain-mappings create \
    --service="$FRONTEND_SVC" \
    --domain="$CUSTOM_DOMAIN" \
    --region="$REGION" \
    --project="$PROJECT_ID" 2>/dev/null || \
    warn "Domain mapping may already exist — check the GCP Console."
  warn "Add the DNS records shown above to your domain registrar (studyspaceapp.in)."
fi

# ─────────────────────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║            Deployment Complete!                      ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${GREEN}Frontend${RESET}  →  $FRONTEND_URL"
echo -e "  ${GREEN}Backend${RESET}   →  $BACKEND_URL"
echo -e "  ${GREEN}API Health${RESET} →  ${BACKEND_URL}/health"
echo -e "  ${GREEN}GCP Console${RESET} → https://console.cloud.google.com/run?project=${PROJECT_ID}"
echo ""
echo -e "${BOLD}─── CI/CD — Auto-deploy on every git push ────────────────────────────${RESET}"
echo -e "  1. Open: ${CYAN}https://console.cloud.google.com/cloud-build/triggers?project=${PROJECT_ID}${RESET}"
echo -e "  2. Create Trigger → Connect GitHub repo (kmarjun99/Study-Space)"
echo -e "  3. Use cloudbuild.yaml, set these substitutions:"
echo -e "     ${CYAN}_REGION${RESET}           = $REGION"
echo -e "     ${CYAN}_REPO${RESET}             = $REPO_NAME"
echo -e "     ${CYAN}_BACKEND_SERVICE${RESET}  = $BACKEND_SVC"
echo -e "     ${CYAN}_FRONTEND_SERVICE${RESET} = $FRONTEND_SVC"
echo -e "     ${CYAN}_VITE_API_URL${RESET}     = $BACKEND_URL"
echo -e "     ${CYAN}_MAPS_KEY${RESET}         = <your-maps-key>"
echo -e "     ${CYAN}_GEMINI_KEY${RESET}       = <your-gemini-key>"
echo -e "     ${CYAN}_CLOUDSQL_INSTANCE${RESET}= $CLOUDSQL_INSTANCE"
echo ""
echo -e "${BOLD}─── To add Razorpay / SendGrid later ────────────────────────────────${RESET}"
echo -e "  echo -n 'YOUR_KEY' | gcloud secrets create RAZORPAY_KEY_ID --data-file=-"
echo -e "  echo -n 'YOUR_SECRET' | gcloud secrets create RAZORPAY_KEY_SECRET --data-file=-"
echo -e "  Then redeploy: gcloud run deploy $BACKEND_SVC --region=$REGION \\"
echo -e "    --set-secrets='RAZORPAY_KEY_ID=RAZORPAY_KEY_ID:latest,RAZORPAY_KEY_SECRET=RAZORPAY_KEY_SECRET:latest'"
echo ""
