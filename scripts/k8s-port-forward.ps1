Write-Host "Starting Finance Tracker port-forwards in separate PowerShell windows..." -ForegroundColor Cyan

Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/frontend 5173:3000"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/user-service 8001:8001"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/transaction-service 8002:8002"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/budget-service 8003:8003"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/account-service 8004:8003"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/categorization-service 8005:8005"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/goal-service 8006:8006"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/ai-service 8007:8004"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/banking-service 8009:8009"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/gateway-service 8010:8010"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/rabbitmq 15672:15672"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/grafana 3001:3000"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/prometheus 9090:9090"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/loki 3100:3100"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/blackbox-exporter 9115:9115"
Start-Process powershell -ArgumentList "kubectl -n finance-tracker port-forward svc/cadvisor 8089:8080"

Write-Host ""
Write-Host "Frontend:     http://localhost:5173" -ForegroundColor Green
Write-Host "Gateway/GQL:  http://localhost:8010/api/v1/graphql" -ForegroundColor Green
Write-Host "RabbitMQ:     http://localhost:15672  guest / guest" -ForegroundColor Green
Write-Host "Grafana:      http://localhost:3001  admin / admin" -ForegroundColor Green
Write-Host "Prometheus:   http://localhost:9090" -ForegroundColor Green
Write-Host ""
Write-Host "Close the opened PowerShell windows or press CTRL+C in each to stop port-forwarding."
