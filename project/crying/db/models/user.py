import datetime
import typing

from tortoise import fields, models

from project.crying.config import TIME_ZONE
from project.crying.db.models.base import AbstractUser

if typing.TYPE_CHECKING:
    from .subscription import Subscription


class Channel(models.Model):
    skin = fields.CharField(100, index=True)
    username = fields.CharField(100, index=True)

    def __str__(self):
        return f"{self.skin} [{self.username}]"

    @property
    def at_username(self):
        return self.username[1:]


class User(AbstractUser):
    subscription: "Subscription"

    @classmethod
    async def count_all(cls) -> int:
        return await cls.all().count()

    @classmethod
    async def count_new_today(cls) -> int:
        date = datetime.datetime.now(TIME_ZONE)
        return await User.filter(
            registered_at__year=date.year,
            registered_at__month=date.month,
            registered_at__day=date.day,
        ).count()
