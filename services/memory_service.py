from models.memory import SessionLocal, Memory

def remember(content):
    session = SessionLocal()
    memory = Memory(content=content)
    session.add(memory)
    session.commit()
    session.close()

def get_memories():
    session = SessionLocal()
    memories = session.query(Memory).all()
    session.close()
    return memories