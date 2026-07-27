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

echo "Deploying Finance Tracker with kustomize..."
kubectl apply -k k8s

echo "Current pods:"
kubectl get pods -n finance-tracker

echo "Done. Wait until all pods are Running/Completed where expected."
echo "Useful command: kubectl get pods -n finance-tracker -w"
