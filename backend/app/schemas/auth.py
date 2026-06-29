from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr                              # rejects malformed emails automatically
    password: str = Field(min_length=8, max_length=128)  # enforce a minimum length


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: str
    is_active: bool

    # lets Pydantic read directly from a SQLAlchemy model object
    model_config = {"from_attributes": True}
