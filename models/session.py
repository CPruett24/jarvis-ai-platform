from sqlalchemy import Column, Integer, DateTime, String
from sqlalchemy.orm import relationship
from datetime import datetime

from models.memory import Base


class Session(Base):

    __tablename__ = "sessions"

    id = Column(
        Integer,
        primary_key=True
    )

    started_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    ended_at = Column(
        DateTime,
        nullable=True
    )

    device = Column(
        String,
        default="Desktop"
    )

    model = Column(
        String,
        default="llama3.1:8b"
    )

    messages = relationship(
        "Conversation",
        back_populates="session"
    )