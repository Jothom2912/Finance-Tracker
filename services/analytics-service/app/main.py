from fastapi import FastAPI

app = FastAPI(title="Analytics Service", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "analytics-service"}
