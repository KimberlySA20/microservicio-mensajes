from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class MessageCreate(BaseModel):
    content: str
    sender_id: str


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender: str = Field(alias="sender_id")
    content: str
    timestamp: datetime
    status: Optional[str] = None
    isRead: Optional[bool] = Field(default=None, alias="is_read")

    class Config:
        populate_by_name = True
        from_attributes = True


class ConversationOut(BaseModel):
    id: int
    name: Optional[str] = None
    avatar: Optional[str] = None
    lastMessage: Optional[str] = None
    lastMessageTime: Optional[str] = None


class ConversationDetailOut(BaseModel):
    id: int
    messages: List[MessageOut]


class CreateConversationIn(BaseModel):
    participantId: str
    currentUserId: str  # ID del usuario que está creando la conversación
    initialMessage: Optional[str] = ""
