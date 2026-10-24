from fastapi import FastAPI

app = FastAPI(title="Car Dealership Inventory API")


@app.get("/health")
def health_check():
    return {"status": "ok"}