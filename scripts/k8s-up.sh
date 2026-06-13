#!/usr/bin/env bash
set -euo pipefail

echo "=== Finance Tracker Kubernetes setup ==="

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

echo "Deploying Finance Tracker with kustomize..."
kubectl apply -k k8s

echo "Current pods:"
kubectl get pods -n finance-tracker

echo "Done. Wait until all pods are Running/Completed where expected."
echo "Useful command: kubectl get pods -n finance-tracker -w"
