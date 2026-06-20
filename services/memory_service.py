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

def get_memory_context():

    memories = get_memories()

    if not memories:
        return "No stored memories."

    memory_text = []

    for memory in memories:
        memory_text.append(
            f"User memory: {memory.content}"
        )

    return "\n".join(memory_text)

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