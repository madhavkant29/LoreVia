from pydantic import BaseModel


class CheckoutBody(BaseModel):
    plan: str
