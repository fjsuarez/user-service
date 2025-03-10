from fastapi import FastAPI, HTTPException
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from contextlib import asynccontextmanager
import firebase_admin
from firebase_admin import credentials, auth, firestore
from models import User, SignupRequest, LoginRequest, AuthResponse
from datetime import datetime

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

app = FastAPI(
    root_path="/api/users",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

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
    
@app.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    try:
        # Create the user in Firebase Authentication
        user = auth.create_user(
            email=request.email,
            password=request.password,
            display_name=f"{request.firstName} {request.lastName}",
            phone_number=request.phoneNumber
        )
        
        # Create a custom token (or you can get an ID token)
        token = auth.create_custom_token(user.uid)
        
        # Store additional user data in Firestore
        user_data = {
            "id": user.uid,
            "firstName": request.firstName,
            "lastName": request.lastName,
            "email": request.email,
            "phoneNumber": request.phoneNumber,
            "isEmailVerified": False,
            "createdAt": datetime.now(),
            "updatedAt": datetime.now(),
        }
        
        # Store in Firestore
        user_ref = app.state.users_ref.document(user.uid)
        user_ref.set(user_data)
        
        return {"token": token, "user": user_data}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    try:
        print(f"Logging in user with email: {request.email}")
        print(f"Logging in user with password: {request.password}")
        # Verify the email/password with Firebase
        user = auth.get_user_by_email(request.email)
        
        # Note: Firebase Admin SDK doesn't have a direct way to verify passwords
        # You'd normally use the Firebase Authentication REST API for this
        # This is a simplified example
        
        # Create a custom token
        token = auth.create_custom_token(user.uid)
        
        print(token)
        # Get user data from Firestore
        user_doc = app.state.users_ref.document(user.uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User record not found")
        
        user_data = user_doc.to_dict()
        
        return {"token": token, "user": user_data}
    
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password")

if __name__ == "__main__":
    import uvicorn
    print(f"PORT {settings.PORT}")
    print(f"DATABASE_URL {settings.DATABASE_URL}")
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)