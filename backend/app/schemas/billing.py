from typing import Literal

from pydantic import BaseModel

PaidPlanCode = Literal[
    "reader_monthly",
    "reader_annual",
    "author_monthly",
    "author_annual",
    "architect_monthly",
    "architect_annual",
    "pro_monthly",
    "pro_annual",
    "power_monthly",
    "power_annual",
]


class CheckoutBody(BaseModel):
    plan: PaidPlanCode
