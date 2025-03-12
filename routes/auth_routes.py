from fastapi import APIRouter, HTTPException, Request
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from datetime import datetime
from models import SignupRequest, LoginRequest, AuthResponse
from services.auth_service import create_firebase_user, exchange_custom_token_for_id_token, verify_email_password
from services.user_service import get_complete_user_data
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest, request_obj: Request):
    users_ref = request_obj.app.state.users_ref
    if not users_ref:
        logger.error("users_ref is not defined in app state")
        raise HTTPException(status_code=500, detail="Database reference not configured")
    
    try:
        # Create Firebase Auth user
        user = await create_firebase_user(
            request.email, 
            request.password,
            request.firstName,
            request.lastName,
            request.phoneNumber
        )
        
        # Create custom token and exchange for ID token
        custom_token = auth.create_custom_token(user.uid)
        id_token = await exchange_custom_token_for_id_token(custom_token)
        
        # Convert datetime to string to ensure it's serializable
        current_time = datetime.now().isoformat()
        
        # Store user data in Firestore
        user_data = {
            "id": user.uid,
            "firstName": request.firstName,
            "lastName": request.lastName,
            "email": request.email,
            "phoneNumber": request.phoneNumber,
            "isEmailVerified": False,
            "onboardingCompleted": False,
            "createdAt": current_time,
            "updatedAt": current_time,
            "userType": "rider",  # Default user type
        }
        
        try:
            user_ref = users_ref.document(user.uid)
            user_ref.set(user_data)
            logger.info(f"User created successfully: {user.uid}")
            
            return {
                "token": id_token,
                "user": user_data
            }
        except Exception as e:
            logger.error(f"Error saving user data to Firestore: {str(e)}")
            # Attempt to clean up the Auth user if Firestore save fails
            try:
                auth.delete_user(user.uid)
            except Exception:
                logger.error("Failed to clean up Firebase Auth user")
            
            raise HTTPException(status_code=500, detail=f"Failed to save user data: {str(e)}")
            
    except FirebaseError as e:
        logger.error(f"Firebase error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")

@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, request_obj: Request):
    users_ref = request_obj.app.state.users_ref
    
    # Verify credentials
    auth_data = await verify_email_password(request.email, request.password)
    id_token = auth_data["idToken"]
    user_id = auth_data["localId"]
    
    # Get user data with helper function
    user_data = await get_complete_user_data(user_id, users_ref)
    if not user_data:
        raise HTTPException(status_code=404, detail="User record not found")
    
    logger.info(f"User logged in: {user_id}")
    return {"token": id_token, "user": user_data}