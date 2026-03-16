from pydantic import BaseModel, Field
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