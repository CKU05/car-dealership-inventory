from pydantic import BaseModel, Field


class RestockRequest(BaseModel):
    quantity: int = Field(gt=0)