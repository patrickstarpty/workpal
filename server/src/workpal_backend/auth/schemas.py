from pydantic import BaseModel

class SendCode(BaseModel):
    email: str

class VerifyCode(SendCode):
    code: str
