Write-Host "Building serverless KEDA job image..."
docker build -t finance-tracker/serverless-health-job:local -f services/serverless-health-job/Dockerfile .
Write-Host "Done. Built finance-tracker/serverless-health-job:local"
