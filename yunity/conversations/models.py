from django.db.models import ForeignKey, TextField, ManyToManyField
from django_enumfield import enum

from yunity.base.base_models import BaseModel, MaxLengthCharField
from yunity.users.models import User


class ConversationType(enum.Enum):
    ONE_ON_ONE = 0
    MULTICHAT = 1


class Conversation(BaseModel):
    participants = ManyToManyField(User)
    type = enum.EnumField(ConversationType, default=ConversationType.ONE_ON_ONE)

    topic = MaxLengthCharField(null=True)


class ConversationMessage(BaseModel):
    author = ForeignKey(User)
    in_conversation = ForeignKey(Conversation, related_name='messages')

    content = TextField()
