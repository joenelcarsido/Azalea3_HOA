from pydantic import BaseModel

class HomeownerCreate(BaseModel):
    house_number: str
    owner_name: str
    username: str
    password: str

class HomeownerOut(BaseModel):
    id: int
    house_number: str
    owner_name: str
    username: str

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str


