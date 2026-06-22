$ErrorActionPreference = "Stop"

$namespace = "finance-tracker"

Write-Host "Starting Finance Tracker port-forwards in this PowerShell window..." -ForegroundColor Cyan

$portForwards = @(
    @{ Name = "Frontend";       Service = "svc/frontend";               Ports = "5173:3000" }
    @{ Name = "User";           Service = "svc/user-service";           Ports = "8001:8001" }
    @{ Name = "Transaction";    Service = "svc/transaction-service";    Ports = "8002:8002" }
    @{ Name = "Budget";         Service = "svc/budget-service";         Ports = "8003:8003" }
    @{ Name = "Account";        Service = "svc/account-service";        Ports = "8004:8003" }
    @{ Name = "Categorization"; Service = "svc/categorization-service"; Ports = "8005:8005" }
    @{ Name = "Goal";           Service = "svc/goal-service";           Ports = "8006:8006" }
    @{ Name = "AI";             Service = "svc/ai-service";             Ports = "8007:8004" }
    @{ Name = "Banking";        Service = "svc/banking-service";        Ports = "8009:8009" }
    @{ Name = "Gateway";        Service = "svc/gateway-service";        Ports = "8010:8010" }
    @{ Name = "RabbitMQ";       Service = "svc/rabbitmq";               Ports = "15672:15672" }
    @{ Name = "Grafana";        Service = "svc/grafana";                Ports = "3001:3000" }
    @{ Name = "Prometheus";     Service = "svc/prometheus";             Ports = "9090:9090" }
    @{ Name = "Loki";           Service = "svc/loki";                   Ports = "3100:3100" }
    @{ Name = "Blackbox";       Service = "svc/blackbox-exporter";      Ports = "9115:9115" }
    @{ Name = "cAdvisor";       Service = "svc/cadvisor";               Ports = "8089:8080" }
    @{ Name = "Saga";           Service = "svc/saga-service";           Ports = "8011:8011" }
)

$jobs = @()

foreach ($pf in $portForwards) {
    Write-Host "Starting $($pf.Name): localhost:$($pf.Ports.Split(':')[0]) -> $($pf.Service)" -ForegroundColor Yellow

    $jobs += Start-Job -Name $pf.Name -ScriptBlock {
        param($namespace, $service, $ports)
        kubectl -n $namespace port-forward $service $ports
    } -ArgumentList $namespace, $pf.Service, $pf.Ports
}

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "Port-forwards started:" -ForegroundColor Green
Write-Host "Frontend:     http://localhost:5173" -ForegroundColor Green
Write-Host "Gateway/GQL:  http://localhost:8010/api/v1/graphql" -ForegroundColor Green
Write-Host "Banking:      http://localhost:8009/health" -ForegroundColor Green
Write-Host "RabbitMQ:     http://localhost:15672  guest / guest" -ForegroundColor Green
Write-Host "Grafana:      http://localhost:3001  admin / admin" -ForegroundColor Green
Write-Host "Prometheus:   http://localhost:9090" -ForegroundColor Green
Write-Host "Saga:         http://localhost:8011/health" -ForegroundColor Green

Write-Host ""
Write-Host "If something fails, check jobs with: Get-Job" -ForegroundColor Cyan
Write-Host "Press ENTER to stop all port-forwards." -ForegroundColor Cyan

Read-Host

Write-Host "Stopping port-forwards..." -ForegroundColor Yellow

$jobs | Stop-Job
$jobs | Remove-Job

Write-Host "All port-forwards stopped." -ForegroundColor Green