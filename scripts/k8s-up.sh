#!/usr/bin/env bash
set -euo pipefail

echo "=== Finance Tracker Kubernetes setup ==="

# k8s/secrets.yaml holder den delte HS256-nøgle og er gitignored (P2-26), så
# et frisk clone har den ikke. Fanget her frem for at lade `kubectl apply -k`
# fejle på en manglende fil i kustomization'en — samme fail-closed som
# compose's ${JWT_SECRET:?}, blot med en besked man kan handle på.
if [ ! -f k8s/secrets.yaml ]; then
  cat >&2 <<'MSG'
k8s/secrets.yaml findes ikke (den er gitignored med vilje).

  cp k8s/secrets.yaml.example k8s/secrets.yaml

Udfyld derefter JWT_SECRET, SECRET_KEY og INTERNAL_API_KEY. JWT_SECRET og
SECRET_KEY skal have samme værdi — det er én delt nøgle, gateway-service
læser den blot under det gamle navn.
MSG
  exit 1
fi

echo "Checking kubectl / Kubernetes cluster..."
kubectl get nodes

echo "Checking Helm..."
if ! command -v helm >/dev/null 2>&1; then
  echo "Helm was not found. Install Helm first: https://helm.sh/docs/intro/install/" >&2
  exit 1
fi
helm version

echo "Installing/upgrading KEDA..."
helm repo add kedacore https://kedacore.github.io/charts --force-update >/dev/null
helm repo update
helm upgrade --install keda kedacore/keda --namespace keda --create-namespace

echo "Waiting for KEDA deployments..."
kubectl rollout status deployment/keda-operator -n keda --timeout=180s
kubectl rollout status deployment/keda-admission-webhooks -n keda --timeout=180s
kubectl rollout status deployment/keda-operator-metrics-apiserver -n keda --timeout=180s

echo "Building all local Docker images..."
./scripts/build-k8s-images.sh

echo "Creating namespace first..."
kubectl apply -f k8s/namespace.yaml

# Enable Banking PEM secret. The private key is gitignored (*.pem) and must NOT
# be committed, so it cannot live in k8s/secrets.yaml — create it here from the
# local file instead. Idempotent: re-applies on every run if the PEM is present.
PEM_FILE="enablebanking-sandbox.pem"
if [ -f "$PEM_FILE" ]; then
  echo "Creating enablebanking-pem secret from $PEM_FILE..."
  kubectl create secret generic enablebanking-pem \
    --namespace finance-tracker \
    --from-file=enablebanking-sandbox.pem="$PEM_FILE" \
    --dry-run=client -o yaml | kubectl apply -f -
else
  echo "WARNING: $PEM_FILE not found in repo root — banking-service cannot reach Enable Banking until it is added (the file is gitignored)." >&2
fi

echo "Applying configuration and infrastructure..."
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -k k8s/infra

wait_for_postgres() {
  deployment="$1"
  user="$2"
  echo "Waiting for $deployment..."
  kubectl rollout status "deployment/$deployment" -n finance-tracker --timeout=180s
  for attempt in $(seq 1 30); do
    if kubectl exec -n finance-tracker "deployment/$deployment" -- pg_isready -U "$user" >/dev/null 2>&1; then
      return 0
    fi
    if [ "$attempt" -eq 30 ]; then
      echo "$deployment did not accept database connections within 150 seconds" >&2
      return 1
    fi
    sleep 5
  done
}

wait_for_postgres postgres user_service
wait_for_postgres postgres-transactions transaction_service
wait_for_postgres postgres-account account_user
wait_for_postgres postgres-categorization categorization_service
wait_for_postgres postgres-budget budget_service
wait_for_postgres postgres-goals goal_service
wait_for_postgres postgres-banking banking_service
wait_for_postgres postgres-saga saga_service
wait_for_postgres postgres-notifications notification_service

echo "Running schema migrations as a separate deployment phase..."
# Completed Job specs do not rerun when applied. Recreate them on every rollout,
# then fail before creating application pods if any schema cannot reach head.
kubectl delete -k k8s/migrations --ignore-not-found=true

migration_jobs=(
  user-migration
  transaction-migration
  account-migration
  categorization-migration
  budget-migration
  goal-migration
  banking-migration
  saga-migration
  notification-migration
)
for job in "${migration_jobs[@]}"; do
  # Apply and await one Job at a time. Docker Desktop runs the Compose and
  # Kubernetes stacks in the same VM; starting nine Python images together was
  # measured OOM-killing first attempts on the 7.8 GiB local runtime (P3-17).
  kubectl apply -f k8s/migrations/migration-jobs.yaml -l "app=$job"
  if ! kubectl wait -n finance-tracker --for=condition=complete "job/$job" --timeout=180s; then
    echo "Migration failed: $job" >&2
    kubectl logs -n finance-tracker "job/$job" --all-containers=true >&2 || true
    exit 1
  fi
done

echo "Applying APIs, workers and the complete validated inventory..."
kubectl apply -k k8s

echo "Current pods:"
kubectl get pods -n finance-tracker

echo "Done. Wait until all pods are Running/Completed where expected."
echo "Useful command: kubectl get pods -n finance-tracker -w"
