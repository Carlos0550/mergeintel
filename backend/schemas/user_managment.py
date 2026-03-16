from pydantic import BaseModel, Field, field_validator
from backend.models.user import UserRole, UserStatus

class CurrentUser(BaseModel):
    id: str = Field(..., description="The id of the user")
    name: str = Field(..., description="The name of the user")
    email: str = Field(..., description="The email of the user")
    role: UserRole = Field(..., description="The role of the user")
    status: UserStatus = Field(..., description="The status of the user")   

class CreateUserRequest(BaseModel):
    name: str = Field(..., description="The name of the user")
    email: str = Field(..., description="The email of the user")
    password: str = Field(..., description="The password of the user")

    @field_validator("email", mode="before")
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email")
        return v.strip().lower()

    @field_validator("password", mode="before")
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v
    
    @field_validator("name", mode="before")
    def validate_name(cls, v: str) -> str:
        return v.strip().lower()