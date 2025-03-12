import httpx
from fastapi import HTTPException
from firebase_admin import auth
from config import settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def exchange_custom_token_for_id_token(custom_token):
    """Exchange Firebase custom token for an ID token"""
    try:
        # Check if custom_token is bytes and convert to string if needed
        if isinstance(custom_token, bytes):
            custom_token = custom_token.decode('utf-8')
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={settings.FIREBASE_API_KEY}",
                json={"token": custom_token, "returnSecureToken": True}
            )
            
            response.raise_for_status()
            token_data = response.json()
            return token_data["idToken"]
    except httpx.HTTPStatusError as e:
        logger.error(f"Token exchange failed: Status {e.response.status_code}")
        
        error_message = "Authentication failed"
        try:
            error_data = e.response.json()
            if "error" in error_data:
                error_message = error_data["error"].get("message", error_message)
        except Exception:
            pass
        raise HTTPException(status_code=401, detail=error_message)
    except Exception as e:
        logger.error(f"Unexpected error during token exchange: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")

async def create_firebase_user(email, password, first_name, last_name, phone_number):
    """Create user in Firebase Authentication"""
    try:
        return auth.create_user(
            email=email,
            password=password,
            display_name=f"{first_name} {last_name}",
            phone_number=phone_number
        )
    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=409, detail="Email already exists")
    except auth.InvalidEmailError:
        raise HTTPException(status_code=400, detail="Invalid email format")
    except auth.PhoneNumberAlreadyExistsError:
        raise HTTPException(status_code=409, detail="Phone number already exists")
    except auth.WeakPasswordError:
        raise HTTPException(status_code=400, detail="Password is too weak")
    except Exception as e:
        logger.error(f"Error creating Firebase user: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

async def verify_email_password(email, password):
    """Verify email/password credentials with Firebase Auth"""
    try:
        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={settings.FIREBASE_API_KEY}",
                json={
                    "email": email,
                    "password": password,
                    "returnSecureToken": True
                }
            )
            auth_response.raise_for_status()
            return auth_response.json()
    except httpx.HTTPStatusError as e:
        error_message = "Invalid email or password"
        try:
            error_data = e.response.json()
            if "error" in error_data:
                error_message = error_data["error"].get("message", error_message)
        except Exception:
            pass
        raise HTTPException(status_code=401, detail=error_message)
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")