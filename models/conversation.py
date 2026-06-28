from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from models.memory import Base


class Conversation(Base):

    __tablename__ = "conversations"

    id = Column(
        Integer,
        primary_key=True
    )

    session_id = Column(
        Integer,
        ForeignKey("sessions.id")
    )

    role = Column(
        String
    )

    message = Column(
        String
    )

    timestamp = Column(
        DateTime,
        default=datetime.utcnow
    )

    session = relationship(
        "Session",
        back_populates="messages"
    )