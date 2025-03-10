from pydantic import BaseModel, Field
from datetime import datetime
from typing import List

class Vehicle(BaseModel):
    vehicleId: str = Field(..., alias="vehicleId")
    make: str
    model: str
    year: int
    licensePlate: str
    capacity: int

class Driver(BaseModel):
    licenseNumber: str = ""
    vehicles: List[Vehicle] = []

class User(BaseModel):
    id: str
    lastName: str
    firstName: str
    email: str
    phoneNumber: str
    profilePictureURL: str | None = None
    isEmailVerified: bool
    createdAt: datetime
    updatedAt: datetime
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
    phoneNumber: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    token: str
    user: dict