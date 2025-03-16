from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
from models import User, OnboardingRequest
from typing import List
from services.user_service import get_complete_user_data, save_user
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
    
    # Parse request body
    try:
        data = await request.json()
        update_request = OnboardingRequest(**data)  # Reuse the same model
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request data: {str(e)}")

    try:
        # Get user reference
        user_ref = users_ref.document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update user profile
        updates = {
            "updatedAt": datetime.now()
        }

        # Add this block to update userType based on isDriver
        if update_request.userType:
            # If userType is explicitly provided in the request, use that
            updates["userType"] = update_request.userType
        elif update_request.isDriver is not None:
            # Otherwise use the isDriver flag
            updates["userType"] = "driver" if update_request.isDriver else "rider"
        
        # Update driver details if applicable
        if update_request.isDriver and update_request.driverDetails:
            driver_ref = user_ref.collection("driver").document("details")
            
            # Update driver details
            driver_data = {
                "licenseNumber": update_request.driverDetails.licenseNumber,
                "isActive": update_request.driverDetails.isActive
            }
            
            # Check if driver document exists
            driver_doc = driver_ref.get()
            if driver_doc.exists:
                driver_ref.update(driver_data)
            else:
                driver_ref.set(driver_data)
            
            # Handle vehicles
            if update_request.driverDetails.vehicles:
                for vehicle in update_request.driverDetails.vehicles:
                    vehicle_ref = driver_ref.collection("vehicles").document(vehicle.vehicleId)
                    
                    # Check if vehicle exists
                    vehicle_doc = vehicle_ref.get()
                    if vehicle_doc.exists:
                        vehicle_ref.update(vehicle.model_dump())
                    else:
                        vehicle_ref.set(vehicle.model_dump())
        
        # Handle case where user is no longer a driver
        elif not update_request.isDriver:
            # Check if driver details exist
            driver_ref = user_ref.collection("driver").document("details")
            driver_doc = driver_ref.get()
            
            if driver_doc.exists:
                # Set driver as inactive rather than deleting
                driver_ref.update({"isActive": False})
        
        # Update the user document
        user_ref.update(updates)
        
        # Return complete updated user data
        updated_user = await get_complete_user_data(user_ref, users_ref)
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
    
    # Parse request body
    try:
        data = await request.json()
        onboarding_request = OnboardingRequest(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request data: {str(e)}")

    try:
        # Get user reference
        user_ref = users_ref.document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update onboarding status
        updates = {
            "onboardingCompleted": True,
            "updatedAt": datetime.now()
        }
        
        # Set user type based on driver selection
        if onboarding_request.isDriver:
            updates["userType"] = "driver"
        else:
            updates["userType"] = "rider"
        
        # If user is a driver, store driver details
        if onboarding_request.isDriver and onboarding_request.driverDetails:
            # Create driver subcollection
            driver_ref = user_ref.collection("driver").document("details")
            driver_data = {
                "licenseNumber": onboarding_request.driverDetails.licenseNumber,
                "isActive": onboarding_request.driverDetails.isActive
            }
            driver_ref.set(driver_data)
            
            # Add vehicles if any
            for vehicle in onboarding_request.driverDetails.vehicles:
                vehicle_ref = driver_ref.collection("vehicles").document(vehicle.vehicleId)
                vehicle_ref.set(vehicle.model_dump())
        
        user_ref.update(updates)
        
        # Return complete user data
        updated_user = await get_complete_user_data(user_ref, users_ref)
        return updated_user
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")

# @router.get("/profile")
# async def get_user_profile(request: Request):
#     users_ref = request.app.state.users_ref
#     user_id = request.headers.get("X-User-ID")
#     if not user_id:
#         raise HTTPException(status_code=401, detail="Missing user ID")
        
#     try:
#         user_data = await get_complete_user_data(user_id, users_ref)
#         if not user_data:
#             raise HTTPException(status_code=404, detail="User profile not found")
        
#         return user_data
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error fetching user profile: {str(e)}")
    