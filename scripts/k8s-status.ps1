Write-Host "Kubernetes nodes" -ForegroundColor Cyan
kubectl get nodes

Write-Host "\nFinance Tracker pods" -ForegroundColor Cyan
kubectl get pods -n finance-tracker

Write-Host "\nFinance Tracker services" -ForegroundColor Cyan
kubectl get svc -n finance-tracker

Write-Host "\nKEDA" -ForegroundColor Cyan
kubectl get pods -n keda
kubectl get scaledjob -n finance-tracker
