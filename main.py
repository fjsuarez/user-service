import os
from fastapi import FastAPI
from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from contextlib import asynccontextmanager
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

class Settings(BaseSettings):
    PORT: int
    DATABASE_URL: str

    model_config = ConfigDict(env_file='.env')
settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    try:
        cred = credentials.Certificate('credentials.json')
        print(cred)
        print(settings.DATABASE_URL)
        firebase_app = firebase_admin.initialize_app(cred, {
            'databaseURL': settings.DATABASE_URL
        })
        db = firestore.client(app=firebase_app, database_id="users")
        users_ref = db.collection("users")
        print("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        print(f"Error initializing Firebase Admin SDK: {e}")

    # makes users_ref available to routes
    app.state.users_ref = users_ref

    # Yield control back to FastAPI to start handling requests
    yield

    # --- Shutdown ---
    try:
        if db:
            print("Closing Firestore client...")  # DEBUG
            db.close()
            print("Firestore client closed.")
        if firebase_app:  # Check if initialization was successful
            firebase_admin.delete_app(firebase_app)
            print("Firebase Admin SDK app deleted successfully.")
    except Exception as e:
        print(f"Error deleting Firebase Admin SDK app: {e}")


app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/")
async def get_users():
    docs = app.state.users_ref.stream()
    users = []
    for doc in docs:
        users.append(doc.to_dict())
    return users

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)