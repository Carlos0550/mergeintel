from typing import Any
from pydantic import BaseModel, Field
class BaseResponse(BaseModel):
    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="The message returned by the request")

class SucessWithData(BaseResponse):
    result: Any = Field(..., description="The data returned by the request")

class ErrorResponse(BaseResponse):
    err: str = Field(..., description="The raw error returned by the request")
    err_code: str = Field(..., description="The error code returned by the request or the service")
    status_code: int = Field(default=400, description="HTTP status code for the error response")
