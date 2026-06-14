$ErrorActionPreference = "Stop"

docker build -t finance-tracker/user-service:local -f services/user-service/Dockerfile .
docker build -t finance-tracker/transaction-service:local -f services/transaction-service/Dockerfile .
docker build -t finance-tracker/account-service:local -f services/account-service/Dockerfile .
docker build -t finance-tracker/categorization-service:local -f services/categorization-service/Dockerfile .
docker build -t finance-tracker/budget-service:local -f services/budget-service/Dockerfile .
docker build -t finance-tracker/goal-service:local -f services/goal-service/Dockerfile .
docker build -t finance-tracker/ai-service:local -f services/ai-service/Dockerfile .
<<<<<<< HEAD
<<<<<<< HEAD
=======
docker build -t finance-tracker/gateway-service:local -f services/gateway-service/Dockerfile .
>>>>>>> origin/master
=======
docker build -t finance-tracker/gateway-service:local -f services/gateway-service/Dockerfile .
>>>>>>> d01fc4595e038fd694df3b484896c83be9662bc1
docker build -t finance-tracker/banking-service:local -f services/banking-service/Dockerfile .
docker build -t finance-tracker/serverless-health-job:local -f services/serverless-health-job/Dockerfile .

if (Test-Path "services/frontend/Dockerfile") {
  docker build -t finance-tracker/frontend:local -f services/frontend/Dockerfile .
} else {
  Write-Host "Skipping frontend image. Copy frontend.Dockerfile to services/frontend/Dockerfile if needed."
}
