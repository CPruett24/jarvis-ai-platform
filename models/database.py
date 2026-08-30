from sqlalchemy import (
    create_engine,
    inspect,
    text,
)

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

def ensure_conversation_source_column():

    inspector = inspect(
        engine
    )

    columns = inspector.get_columns(
        "conversations"
    )

    column_names = {
        column["name"]
        for column in columns
    }

    if "source" in column_names:
        return

    with engine.begin() as connection:

        connection.execute(
            text(
                "ALTER TABLE conversations "
                "ADD COLUMN source VARCHAR"
            )
        )

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

    ensure_conversation_source_column()