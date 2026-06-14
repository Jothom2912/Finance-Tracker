# Finance Tracker Kubernetes + KEDA Guide

This guide explains how to run the Finance Tracker project in a local Kubernetes cluster, similar to how `docker compose up` starts the local Docker Compose setup.

The setup uses:

- Docker Desktop Kubernetes as the local Kubernetes cluster
- Kubernetes Deployments, Services, ConfigMaps, Secrets and PersistentVolumeClaims
- RabbitMQ for asynchronous event communication
- KEDA ScaledJob for a serverless-style background task
- Local Docker images with `imagePullPolicy: Never`

## 1. Prerequisites

Each group member needs:

- Docker Desktop
- Kubernetes enabled in Docker Desktop
- kubectl
- Helm
- Git

Check Kubernetes:

```powershell
kubectl get nodes
```

Expected result:

```text
docker-desktop   Ready
```

Check Helm:

```powershell
helm version
```

If Helm is missing on Windows, install it with:

```powershell
winget install Helm.Helm
```

Close and reopen PowerShell afterwards.

## 2. Start the full Kubernetes setup

From the project root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\k8s-up.ps1
```

The script will:

1. Check that Kubernetes is running
2. Install/upgrade KEDA with Helm
3. Build all required local Docker images
4. Apply the full Kubernetes setup with `kubectl apply -k k8s`
5. Show the current pod status

Wait until the pods are ready:

```powershell
kubectl get pods -n finance-tracker -w
```

Most pods should become `Running`. One-off jobs such as the Ollama model pull or KEDA init job may show `Completed`.

## 3. What `k8s/kustomization.yaml` does

The file `k8s/kustomization.yaml` gathers the project YAML files into one deployable Kubernetes setup.

Instead of running all these commands manually:

```powershell
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/infra/
kubectl apply -f k8s/apps/
kubectl apply -f k8s/workers/
kubectl apply -f k8s/keda/
```

we can run:

```powershell
kubectl apply -k k8s
```

This is the Kubernetes equivalent of starting a composed setup, similar in spirit to:

```powershell
docker compose up -d
```

Important: Kubernetes YAML does not build Docker images. That is why `scripts/k8s-up.ps1` first runs `scripts/build-k8s-images.ps1`.

## 4. Start port-forwarding for local browser access

Kubernetes Services are internal to the cluster. To reach them from your browser/Postman, run:

```powershell
.\scripts\k8s-port-forward.ps1
```

This opens separate PowerShell windows for the required port-forwards.

Important URLs:

```text
Frontend:     http://localhost:5173
Gateway/GQL:  http://localhost:8010/api/v1/graphql
RabbitMQ:     http://localhost:15672  guest / guest
```

Useful forwarded backend ports:

```text
user-service:             http://localhost:8001/health
transaction-service:      http://localhost:8002/health
budget-service:           http://localhost:8003/health
account-service:          http://localhost:8004/health
categorization-service:   http://localhost:8005/health
goal-service:             http://localhost:8006/health
ai-service:               http://localhost:8007/health
banking-service:          http://localhost:8009/health
gateway-service:          http://localhost:8010/health
```

Stop port-forwarding by closing the opened PowerShell windows or pressing `CTRL+C` in each window.

## 5. Test that everything is running

```powershell
.\scripts\k8s-status.ps1
```

Or manually:

```powershell
kubectl get pods -n finance-tracker
kubectl get svc -n finance-tracker
kubectl get scaledjob -n finance-tracker
```

## 6. KEDA / serverless demo

The KEDA part simulates a serverless function.

Flow:

```text
RabbitMQ queue receives a message
→ KEDA sees queue length > threshold
→ KEDA starts a Kubernetes Job
→ the job checks health endpoints for the services
→ the job logs a JSON report
→ the job exits
```

Run the demo:

```powershell
.\scripts\keda-demo.ps1
```

Then find a completed KEDA job pod:

```powershell
kubectl get pods -n finance-tracker | findstr serverless-health
```

Read logs from one of the `serverless-health-scaledjob-*` pods:

```powershell
kubectl logs <serverless-health-scaledjob-pod-name> -n finance-tracker
```

The log should show a JSON health report for services such as:

- user-service
- transaction-service
- account-service
- categorization-service
- budget-service
- goal-service
- monolith/read gateway

RabbitMQ UI can also show the queue:

```text
serverless.health.requests
```

After the KEDA jobs process the messages, the queue should return to `Ready: 0`.

## 7. Useful Kubernetes commands

Show pods:

```powershell
kubectl get pods -n finance-tracker
```

Show services:

```powershell
kubectl get svc -n finance-tracker
```

Show logs for a deployment:

```powershell
kubectl logs deployment/user-service -n finance-tracker
```

Describe a broken pod:

```powershell
kubectl describe pod <pod-name> -n finance-tracker
```

Read previous crash logs:

```powershell
kubectl logs <pod-name> -n finance-tracker --previous
```

Show KEDA:

```powershell
kubectl get pods -n keda
kubectl get scaledjob -n finance-tracker
kubectl describe scaledjob serverless-health-scaledjob -n finance-tracker
```

## 8. Stop for the day

You do not need to delete Kubernetes resources.

1. Stop all port-forward terminals with `CTRL+C`
2. Close Docker Desktop if needed
3. Start Docker Desktop again tomorrow
4. Check:

```powershell
kubectl get nodes
kubectl get pods -n finance-tracker
```

Then start port-forwarding again:

```powershell
.\scripts\k8s-port-forward.ps1
```

## 9. Delete the local Kubernetes environment

Only use this if you want to start over from scratch:

```powershell
.\scripts\k8s-down.ps1
```

This deletes the `finance-tracker` namespace and the resources inside it. It does not uninstall KEDA itself.

## 10. What to say at the exam

Short explanation:

> We deploy Finance Tracker to a local Kubernetes cluster using Docker Desktop. Each microservice runs as its own Deployment and Pod, and each has a Kubernetes Service for internal DNS-based communication. Databases, RabbitMQ, Redis and Ollama are also deployed inside the cluster. Long-running workers consume RabbitMQ events, while KEDA is used to simulate a serverless function through a ScaledJob that starts only when messages appear in a RabbitMQ queue.

KEDA explanation:

> The serverless health job is not a long-running worker. It scales from zero when RabbitMQ receives messages in `serverless.health.requests`. KEDA creates Kubernetes Jobs, each job processes a message, performs health checks against the services, logs a report and exits again.
