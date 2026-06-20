from models.memory import SessionLocal, Memory

def remember(content, category="general"):
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

def search_memories(keyword):
    session = SessionLocal()
    memories = (session.query(Memory).filter(Memory.content.contains(keyword)).all())
    session.close()
    return memories

def delete_memory(keyword):
    session = SessionLocal()

    memory = (session.query(Memory).filter(Memory.content.contains(keyword)).first())

    if memory:
        session.delete(memory)
        session.commit()

    session.close()

    return memory is not None