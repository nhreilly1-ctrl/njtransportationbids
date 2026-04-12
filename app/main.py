from fastapi import FastAPI

app = FastAPI(title="NJ Bid Registry")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/ready")
def ready():
    return {"ok": True}

@app.get("/")
def root():
    return {
        "name": "NJ Bid Registry",
        "status": "running"
    }
