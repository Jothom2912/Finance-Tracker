$ErrorActionPreference = "Stop"

Write-Host "=== Finance Tracker Kubernetes setup ===" -ForegroundColor Cyan

Write-Host "Checking kubectl / Kubernetes cluster..." -ForegroundColor Cyan
kubectl get nodes

Write-Host "Checking Helm..." -ForegroundColor Cyan
if (-not (Get-Command helm -ErrorAction SilentlyContinue)) {
  Write-Host "Helm was not found. Install it with: winget install Helm.Helm" -ForegroundColor Red
  throw "Helm is required to install KEDA."
}
helm version

Write-Host "Installing/upgrading KEDA..." -ForegroundColor Cyan
helm repo add kedacore https://kedacore.github.io/charts --force-update | Out-Null
helm repo update
helm upgrade --install keda kedacore/keda --namespace keda --create-namespace

Write-Host "Waiting for KEDA deployments..." -ForegroundColor Cyan
kubectl rollout status deployment/keda-operator -n keda --timeout=180s
kubectl rollout status deployment/keda-admission-webhooks -n keda --timeout=180s
kubectl rollout status deployment/keda-operator-metrics-apiserver -n keda --timeout=180s


Write-Host "Installing/upgrading metrics-server..." -ForegroundColor Cyan
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

Write-Host "Patching metrics-server for Docker Desktop..." -ForegroundColor Cyan

$metricsArgs = kubectl get deployment metrics-server -n kube-system -o jsonpath="{.spec.template.spec.containers[0].args}" 2>$null

if ($metricsArgs -notlike "*--kubelet-insecure-tls*") {
  @'
[
  {
    "op": "add",
    "path": "/spec/template/spec/containers/0/args/-",
    "value": "--kubelet-insecure-tls"
  }
]
'@ | Set-Content metrics-server-patch.json

  kubectl patch deployment metrics-server -n kube-system --type=json --patch-file metrics-server-patch.json
  Remove-Item metrics-server-patch.json -ErrorAction SilentlyContinue
}

kubectl rollout status deployment/metrics-server -n kube-system --timeout=180s

Write-Host "Building all local Docker images..." -ForegroundColor Cyan
.\scripts\build-k8s-images.ps1

Write-Host "Creating namespace first..." -ForegroundColor Cyan
kubectl apply -f k8s/namespace.yaml

Write-Host "Deploying Finance Tracker with kustomize..." -ForegroundColor Cyan
kubectl apply -k k8s

Write-Host "\nCurrent pods:" -ForegroundColor Cyan
kubectl get pods -n finance-tracker

Write-Host "\nDone. Wait until all pods are Running/Completed where expected." -ForegroundColor Green
Write-Host "Useful command: kubectl get pods -n finance-tracker -w"
