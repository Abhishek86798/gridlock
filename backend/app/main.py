from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import hotspots, analytics

app = FastAPI(title="Gridlock Parking Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hotspots.router)
app.include_router(analytics.router)

@app.get("/")
def read_root():
    return {"message": "Gridlock API is running"}
