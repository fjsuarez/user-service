from fastapi import FastAPI
from config import settings
from firebase_client import lifespan
from routes import auth_routes, user_routes

app = FastAPI(
    root_path="/api/users",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Include routers
app.include_router(auth_routes.router, tags=["Authentication"])
app.include_router(user_routes.router, tags=["Users"])

if __name__ == "__main__":
    import uvicorn
    print(f"PORT {settings.PORT}")
    print(f"DATABASE_URL {settings.DATABASE_URL}")
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)