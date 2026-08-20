from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path


DATABASE_URL = "sqlite:///data/jarvis.db"

engine = create_engine(
    DATABASE_URL
)

SessionLocal = sessionmaker(
    bind=engine
)

Base = declarative_base()

def initialize_database():

    from models import (
        Memory,
        Goal,
        Session,
        Conversation,
    )

    print("\n===== DATABASE INFO =====")
    print(
        "Database URL:",
        DATABASE_URL,
    )

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