from pydantic import BaseModel
from datetime import datetime
from typing import List, Literal

class Vehicle(BaseModel):
    vehicleId: str
    make: str
    model: str
    year: int
    licensePlate: str
    capacity: int = 4

class Driver(BaseModel):
    licenseNumber: str
    vehicles: List[Vehicle] = []
    isActive: bool = True

class User(BaseModel):
    id: str
    firstName: str
    lastName: str
    email: str
    phoneNumber: str
    profilePictureURL: str | None = None
    isEmailVerified: bool = False
    createdAt: datetime
    updatedAt: datetime
    onboardingCompleted: bool = False
    userType: Literal["rider", "driver"] = "rider"
    driver: Driver | None = None 

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

class SignupRequest(BaseModel):
    email: str
    password: str
    firstName: str
    lastName: str
    phoneNumber: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    token: str
    user: dict

class OnboardingRequest(BaseModel):
    isDriver: bool
    userType: Literal["rider", "driver"] | None = None
    driverDetails: Driver | None = None