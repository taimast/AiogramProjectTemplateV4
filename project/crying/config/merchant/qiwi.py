import datetime
from typing import Optional

from glQiwiApi import QiwiP2PClient
from glQiwiApi.qiwi.clients.p2p.types import Bill
from pydantic import validator

from .base import Merchant, PAYMENT_LIFETIME, TIME_ZONE


# todo L1 24.11.2022 18:29 taima: Использовать кастомную платежную систему вместо модуля glQiwiApi
#  Каждый раз открывается и закрывается сессия, что не есть хорошо
class Qiwi(Merchant):
    client: Optional[QiwiP2PClient]

    class Config:
        arbitrary_types_allowed = True

    @validator("client", always=True)
    def client_validator(cls, v, values):
        if not v:
            api_key = values.get("api_key")
            v = QiwiP2PClient(secret_p2p=api_key.get_secret_value())
        return v

    async def create_invoice(
            self,
            amount: int | float | str,
            description: str = None,
            order_id: str = None,
            email: str = None,
    ) -> Bill:
        return await self.client.create_p2p_bill(
            amount=amount,
            comment=description or f"Product {amount}",
            expire_at=datetime.datetime.now(TIME_ZONE) + datetime.timedelta(seconds=PAYMENT_LIFETIME),
        )

    async def is_paid(self, invoice_id: str) -> bool:
        return (await self.client.get_bill_status(invoice_id)) == "PAID"
