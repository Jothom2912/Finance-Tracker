Write-Host "This will delete the finance-tracker namespace and all Kubernetes resources inside it." -ForegroundColor Yellow
Write-Host "It may also delete local Kubernetes database volumes/PVCs for the project." -ForegroundColor Yellow
$answer = Read-Host "Type DELETE to continue"

if ($answer -ne "DELETE") {
  Write-Host "Aborted."
  exit 0
}

kubectl delete namespace finance-tracker --ignore-not-found
Write-Host "finance-tracker namespace deleted. KEDA itself is not removed." -ForegroundColor Green
