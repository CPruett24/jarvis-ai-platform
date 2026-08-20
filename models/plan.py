from datetime import datetime, UTC

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
)

from models.database import Base


class Plan(Base):

    __tablename__ = "plans"

    id = Column(
        Integer,
        primary_key=True,
    )

    goal_id = Column(
        Integer,
        ForeignKey("goals.id"),
        nullable=False,
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
        default="draft",
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