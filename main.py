from fastapi import FastAPI, HTTPException, Request
import httpx
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from contextlib import asynccontextmanager
import firebase_admin
from firebase_admin import credentials, firestore
from models import User

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
        firebase_app = firebase_admin.initialize_app(cred, {
            'databaseURL': settings.DATABASE_URL
        })
        db = firestore.client(app=firebase_app, database_id="users")
        users_ref = db.collection("users")
        print("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        print(f"Error initializing Firebase Admin SDK: {e}")

    app.state.users_ref = users_ref
    yield

    # --- Shutdown ---
    try:
        if db:
            print("Closing Firestore client...")
            db.close()
            print("Firestore client closed.")
        if firebase_app:
            firebase_admin.delete_app(firebase_app)
            print("Firebase Admin SDK app deleted successfully.")
    except Exception as e:
        print(f"Error deleting Firebase Admin SDK app: {e}")

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Python
@app.get("/")
async def get_users():
    docs = app.state.users_ref.stream()
    users = []
    for doc in docs:
        user_data = doc.to_dict()

        driver_docs = doc.reference.collection("driver").stream()
        drivers = []
        for driver in driver_docs:
            driver_data = driver.to_dict()
            vehicle_docs = driver.reference.collection("vehicle").stream()
            vehicles = [vehicle.to_dict() for vehicle in vehicle_docs]
            driver_data["vehicles"] = vehicles
            drivers.append(driver_data)
        
        if drivers:
            user_data["driver"] = drivers[0]
        else:
            user_data["driver"] = None
        
        try:
            user_model = User.model_validate(user_data)
            users.append(user_model.model_dump())
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error parsing user document: {exc}")
    return users

@app.post("/")
async def create_user(user: User):
    user_data = user.model_dump()
    try:
        user_ref = app.state.users_ref.document(user_data["id"])
        user_ref.set({k: v for k, v in user_data.items() if k != "driver"})
        
        driver_info = user_data.get("driver")
        if driver_info and driver_info.get("licenseNumber"):
            driver_ref = user_ref.collection("driver").document("driver")
            driver_data = {k: v for k, v in driver_info.items() if k != "vehicles"}
            driver_ref.set(driver_data)
            vehicles = driver_info.get("vehicles", [])
            for vehicle in vehicles:
                vehicle_ref = driver_ref.collection("vehicle").document(vehicle["vehicleId"])
                vehicle_ref.set(vehicle)
        return user_data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error creating user document: {exc}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)