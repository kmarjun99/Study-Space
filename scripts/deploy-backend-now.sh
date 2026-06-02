#!/usr/bin/env bash
#
# One-shot backend deploy. Skip the Cloud Build trigger entirely and run
# the full backend build + push + deploy directly from your machine.
#
# Why this exists: the Cloud Build trigger pointed at cloudbuild.yaml
# has been silently failing to fire (or failing to deploy) for at least
# 17 commits since 2026-05-31. Every backend fix — GST split, mySpace
# rebrand, security hardening, the 7s2a rollback fix, route fixes — is
# stuck on main waiting for it. This script is the manual fallback so
# the deploy isn't dependent on whatever's wrong with the trigger.
#
# Prereqs (one-time):
#   1. gcloud SDK installed             https://cloud.google.com/sdk/install
#   2. gcloud auth login                (your Google account)
#   3. gcloud config set project sspace-app-2026
#
# Usage:
#   ./scripts/deploy-backend-now.sh
#
# What it does:
#   * Builds the backend image with $COMMIT_SHA tag = current git HEAD
#   * Pushes to Artifact Registry: asia-south1-docker.pkg.dev
#   * Deploys to Cloud Run service `study-space-backend` in asia-south1
#   * Verifies /health responds with "mySpace API" and the commit SHA
#
# Total runtime: ~4-5 minutes.

set -euo pipefail

# --- Config (matches cloudbuild.yaml substitutions) ---
REGION="${REGION:-asia-south1}"
REPO="${REPO:-study-space}"
BACKEND_SERVICE="${BACKEND_SERVICE:-study-space-backend}"
CLOUDSQL_INSTANCE="${CLOUDSQL_INSTANCE:-}"  # required — see error below
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "❌ PROJECT_ID not set. Run: gcloud config set project YOUR_PROJECT" >&2
  exit 1
fi

if [[ -z "$CLOUDSQL_INSTANCE" ]]; then
  echo "⚠️  CLOUDSQL_INSTANCE is empty. If your backend uses Cloud SQL," >&2
  echo "    set it: CLOUDSQL_INSTANCE='project:region:instance' $0" >&2
  echo "    Continuing without --add-cloudsql-instances; if the backend" >&2
  echo "    can't reach the DB it will fail health-check during deploy." >&2
fi

COMMIT_SHA="$(git -C "$(dirname "$0")/.." rev-parse HEAD)"
SHORT_SHA="${COMMIT_SHA:0:8}"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/backend:${COMMIT_SHA}"
IMAGE_LATEST="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/backend:latest"

echo "📦 Building backend image…"
echo "    SHA:     $SHORT_SHA"
echo "    Image:   $IMAGE"

cd "$(dirname "$0")/.."

# Build with the BUILD_SHA + BUILD_TIME args so /health surfaces them
docker buildx build \
  --platform=linux/amd64 \
  --build-arg "BUILD_SHA=$COMMIT_SHA" \
  --build-arg "BUILD_TIME=$BUILD_TIME" \
  -t "$IMAGE" \
  -t "$IMAGE_LATEST" \
  -f backend/Dockerfile \
  backend/

echo ""
echo "📤 Pushing to Artifact Registry…"
docker push "$IMAGE"
docker push "$IMAGE_LATEST"

echo ""
echo "🚀 Deploying to Cloud Run…"
DEPLOY_ARGS=(
  run deploy "$BACKEND_SERVICE"
  --image="$IMAGE"
  --region="$REGION"
  --platform=managed
  --allow-unauthenticated
  --port=8000
  --memory=512Mi
  --cpu=1
  --min-instances=0
  --max-instances=10
  --set-secrets=DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest,SENDGRID_API_KEY=SENDGRID_API_KEY:latest,RAZORPAY_KEY_ID=RAZORPAY_KEY_ID:latest,RAZORPAY_KEY_SECRET=RAZORPAY_KEY_SECRET:latest,mail_username=MAIL_USERNAME:latest,mail_password=MAIL_PASSWORD:latest
  --set-env-vars=ENVIRONMENT=production,ALGORITHM=HS256,PAYMENT_DEMO_MODE=false
)
if [[ -n "$CLOUDSQL_INSTANCE" ]]; then
  DEPLOY_ARGS+=(--add-cloudsql-instances="$CLOUDSQL_INSTANCE")
fi
gcloud "${DEPLOY_ARGS[@]}"

echo ""
echo "✅ Deploy submitted. Verifying /health…"
sleep 5

SERVICE_URL=$(gcloud run services describe "$BACKEND_SERVICE" --region "$REGION" --format='value(status.url)')
HEALTH=$(curl -s "$SERVICE_URL/health" || echo "(health check unreachable)")

echo ""
echo "🩺 /health response:"
echo "    $HEALTH"
echo ""

if echo "$HEALTH" | grep -q "$SHORT_SHA"; then
  echo "✅ build_sha matches HEAD ($SHORT_SHA) — deploy succeeded."
elif echo "$HEALTH" | grep -q "mySpace API"; then
  echo "✅ service name is 'mySpace API' — deploy succeeded (older build, no build_sha yet)."
else
  echo "⚠️  /health still shows the OLD service name. The deploy may have failed to land traffic."
  echo "    Check Cloud Run console → Revisions → look for the newest one + its 'Reason' if it didn't get traffic."
  echo "    The likely cause is the new container failed startup health check (curl /health timed out)."
  echo "    Inspect logs: gcloud run services logs read $BACKEND_SERVICE --region=$REGION --limit=50"
  exit 1
fi
