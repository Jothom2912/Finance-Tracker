$ErrorActionPreference = "Stop"

Write-Host "Publishing demo messages to RabbitMQ queue serverless.health.requests..." -ForegroundColor Cyan
kubectl delete job serverless-health-publish -n finance-tracker --ignore-not-found
kubectl apply -f k8s/keda/serverless-health-publish-job.yaml

Write-Host "Waiting for KEDA to create serverless jobs..." -ForegroundColor Cyan
Start-Sleep -Seconds 12

Write-Host "\nServerless jobs:" -ForegroundColor Cyan
kubectl get jobs -n finance-tracker | findstr serverless-health

Write-Host "\nServerless pods:" -ForegroundColor Cyan
kubectl get pods -n finance-tracker | findstr serverless-health

Write-Host "\nTo read a completed serverless job log, run:" -ForegroundColor Green
Write-Host "kubectl logs <serverless-health-scaledjob-pod-name> -n finance-tracker"
