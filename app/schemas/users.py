import uuid

from pydantic import BaseModel, Field

class UserBase(BaseModel):
    """Base schema for user data"""
    #TODO: to modify
    id: uuid.UUID = Field(..., description="User unique identifier")
    email: str = Field(..., max_length=255, description="User email address")
    first_name: str = Field(..., max_length=100, description="User's first name")
    last_name: str = Field(..., max_length=100, description="User's last name")
    user_type: str = Field(..., description="Type of user (e.g., admin, user)")