from datetime import datetime, UTC

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
)

from models.database import Base


class Goal(Base):

    __tablename__ = "goals"

    id = Column(
        Integer,
        primary_key=True,
    )

    title = Column(
        String,
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    status = Column(
        String,
        nullable=False,
        default="planned",
    )

    priority = Column(
        String,
        nullable=False,
        default="normal",
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
    )

    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )