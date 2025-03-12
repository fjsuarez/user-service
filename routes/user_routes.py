from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
from models import User, OnboardingRequest
from services.user_service import get_complete_user_data, get_driver_data, save_user

router = APIRouter()

@router.get("/")
async def get_users(request: Request):
    users_ref = request.app.state.users_ref
    docs = users_ref.stream()
    users = []
    
    for doc in docs:
        user_data = doc.to_dict()
        driver_data = await get_driver_data(doc.reference)
        user_data["driver"] = driver_data
        
        try:
            user_model = User.model_validate(user_data)
            users.append(user_model.model_dump())
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error parsing user document: {exc}")
    
    return users

@router.post("/")
async def create_user(user: User, request: Request):
    users_ref = request.app.state.users_ref
    user_data = user.model_dump()
    return await save_user(user_data, users_ref)

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

@router.get("/profile")
async def get_user_profile(request: Request):
    users_ref = request.app.state.users_ref
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user ID")
        
    try:
        user_data = await get_complete_user_data(user_id, users_ref)
        if not user_data:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        return user_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user profile: {str(e)}")
    
@router.patch("/profile")
async def update_user_profile(request: Request):
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