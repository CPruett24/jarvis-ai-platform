from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, UTC
from sqlalchemy import DateTime

DATABASE_URL = "sqlite:///jarvis.db"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    
    category = Column(String, nullable=True, default="general")

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

Base.metadata.create_all(bind=engine)