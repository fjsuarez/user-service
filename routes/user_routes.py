from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
from models import User, OnboardingRequest
from typing import List
from services.user_service import get_complete_user_data, save_user, update_user_profile
from firebase_admin import auth

router = APIRouter()

@router.get("/")
async def get_user(request: Request, response_model=User):
    user_id = request.headers.get("X-User-ID", "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing User ID")
    users_ref = request.app.state.users_ref
    user_ref = users_ref.document(user_id)
    try:
        user_data = await get_complete_user_data(user_ref, users_ref)
    except Exception as e:
        print(type(e))
        raise HTTPException(status_code=500, detail="Unknown Error")
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    return user_data

@router.post("/")
async def create_user(request: Request):
    users_ref = request.app.state.users_ref
    uid = request.headers.get("X-User-ID")
    if not uid:
        raise HTTPException(status_code=401, detail="Missing user ID")
    try:
        print("Creating user")
        data = await request.json()
        data['id'] = uid
        data['createdAt'] = datetime.now()
        data['updatedAt'] = datetime.now()
        data['onboardingCompleted'] = False
        data['userType'] = "rider"
        print("Updating user")
        auth.update_user(uid=uid,
                         display_name=f"{data['firstName']} {data['lastName']}",
                         phone_number=data['phoneNumber'])
        print("Saving user")
        profile = await save_user(data, users_ref)
        print("User created")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unknown Error: {str(e)}")
    return profile

@router.patch("/")
async def update_user(request: Request):
    users_ref = request.app.state.users_ref
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user ID")
    try:
        data = await request.json()
        update_request = OnboardingRequest(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request data: {str(e)}")
    try:
        user_ref = users_ref.document(user_id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        updates = {
            "updatedAt": datetime.now()
        }
        if update_request.userType:
            updates["userType"] = update_request.userType
        elif update_request.isDriver is not None:
            updates["userType"] = "driver" if update_request.isDriver else "rider"
        driver_details = None
        vehicles = None
        if update_request.isDriver and update_request.driverDetails:
            driver_details = {
                "licenseNumber": update_request.driverDetails.licenseNumber,
                "isActive": update_request.driverDetails.isActive
            }
            vehicles = update_request.driverDetails.vehicles
        elif update_request.isDriver is False:
            driver_ref = user_ref.collection("driver").document("details")
            driver_doc = driver_ref.get()
            if driver_doc.exists:
                driver_details = {"isActive": False}
        updated_user = await update_user_profile(user_ref, updates, driver_details, vehicles)
        return updated_user
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user profile: {str(e)}")

@router.get("/all")
async def get_users(request: Request, response_model=List[User]):
    users_ref = request.app.state.users_ref
    docs = users_ref.stream()
    users = []
    for doc in docs:
        try:
            user_data = await get_complete_user_data(doc.reference, users_ref)
            users.append(user_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unknown Error: {str(e)}")
    return users

@router.post("/onboarding")
async def complete_onboarding(request: Request):
    users_ref = request.app.state.users_ref
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user ID")
    try:
        data = await request.json()
        onboarding_request = OnboardingRequest(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request data: {str(e)}")
    try:
        user_ref = users_ref.document(user_id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        updates = {
            "onboardingCompleted": True,
            "updatedAt": datetime.now(),
            "userType": "driver" if onboarding_request.isDriver else "rider"
        }
        driver_details = None
        vehicles = None
        if onboarding_request.isDriver and onboarding_request.driverDetails:
            driver_details = {
                "licenseNumber": onboarding_request.driverDetails.licenseNumber,
                "isActive": onboarding_request.driverDetails.isActive
            }
            vehicles = onboarding_request.driverDetails.vehicles
        updated_user = await update_user_profile(user_ref, updates, driver_details, vehicles)
        return updated_user
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")