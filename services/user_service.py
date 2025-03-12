from fastapi import HTTPException

# Get driver information for a user
async def get_driver_data(user_ref):
    """Get driver data including vehicles for a user reference"""
    driver_doc = user_ref.collection("driver").document("details").get()
    if not driver_doc.exists:
        return None
    
    driver_data = driver_doc.to_dict()
    vehicles = driver_doc.reference.collection("vehicles").stream()
    driver_data["vehicles"] = [vehicle.to_dict() for vehicle in vehicles]
    return driver_data

async def get_complete_user_data(user_ref, users_ref):
    """Get complete user data including driver status and user type"""
    if isinstance(user_ref, str):
        user_ref = users_ref.document(user_ref)
    
    user_doc = user_ref.get()
    if not user_doc.exists:
        return None
    
    user_data = user_doc.to_dict()
    driver_data = await get_driver_data(user_ref)
    
    if driver_data:
        # Include driver data in response if it exists
        user_data["driver"] = driver_data
    else:
        # No driver data found
        user_data["driver"] = None
    
    return user_data

async def save_user(user_data, users_ref):
    """Save user data to firestore, handling driver subcollection"""
    try:
        user_ref = users_ref.document(user_data["id"])
        
        # Save basic user data (without driver field)
        main_data = {k: v for k, v in user_data.items() if k != "driver"}
        user_ref.set(main_data)
        
        # Handle driver information if present
        driver_info = user_data.get("driver")
        if driver_info and driver_info.get("licenseNumber"):
            driver_ref = user_ref.collection("driver").document("details")
            driver_data = {k: v for k, v in driver_info.items() if k != "vehicles"}
            driver_ref.set(driver_data)
            
            # Save vehicles
            vehicles = driver_info.get("vehicles", [])
            for vehicle in vehicles:
                vehicle_ref = driver_ref.collection("vehicles").document(vehicle["vehicleId"])
                vehicle_ref.set(vehicle)
        
        return user_data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error saving user document: {exc}")