import streamlit as st
from services.memory_service import get_memories
from services.workspace_service import open_workspace
from services.conversation_service import get_history
from services.status_service import load_status
from streamlit_autorefresh import st_autorefresh

memories = get_memories() 
status = load_status()

st.set_page_config(
    page_title="JARVIS",
    page_icon="🤖",
    layout="wide"
)

st_autorefresh(
    interval=2000,
    key="jarvis_refresh"
)

st.title("🤖 JARVIS")

st.success("JARVIS Online")

left_col, center_col, right_col = st.columns(3)

with left_col:

    st.subheader("System Status")

    st.metric(
        "Status",
        status["status"]
    )

    st.metric(
        "AI Model",
        "llama3.1:8b"
    )

    st.metric(
        "Memories",
        len(memories)
    )

with center_col:

    st.subheader("Workspace Launcher")

    if st.button("🚀 Coding Workspace"):
        open_workspace("coding")

    if st.button("☁️ AWS Workspace"):
        open_workspace("aws")

with right_col:

    st.subheader("Live Activity")

    st.write(
        f"**Status:** {status['status']}"
    )

    st.write(
        f"**Last Command:** {status['last_command']}"
    )

    st.write(
        f"**Last Response:** {status['last_response']}"
    )

st.subheader(f"Memories ({len(memories)})")

for memory in memories:
    st.info(memory.content)

st.subheader("Recent Conversation")

history = get_history()

if not history:
    st.write("No conversation history yet.")

else:

    for message in history:

        if message["role"] == "user":
            st.markdown(
                f"**🧑 You:** {message['content']}"
            )

        elif message["role"] == "assistant":
            st.markdown(
                f"**🤖 JARVIS:** {message['content']}"
            )
