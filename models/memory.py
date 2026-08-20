from datetime import datetime, UTC

from sqlalchemy import Column, Integer, String, DateTime

from models.database import Base

from models.database import (
    SessionLocal,
    engine,
)

from pathlib import Path


class Memory(Base):

    __tablename__ = "memories"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    content = Column(
        String,
        nullable=False,
    )

    category = Column(
        String,
        nullable=True,
        default="general",
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
    )

def initialize_database():

    print("\n===== DATABASE INFO =====")
    print("Database URL:", "sqlite:///data/jarvis.db")
    print(
        "Database file:",
        Path(
            "data/jarvis.db"
        ).resolve(),
    )

    print(
        "Registered tables:",
        list(
            Base.metadata.tables.keys()
        ),
    )

    print("=========================\n")

    Base.metadata.create_all(
        bind=engine
    )