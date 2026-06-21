from services.speaker import speak
import subprocess
from datetime import datetime
import webbrowser
from services.memory_service import remember, get_memories, search_memories, delete_memory

def remember_command(command):
    memory = command.replace("remember ", "", 1).strip()

    remember(memory)
    speak("Got that stored Chandler.")

def recall_memories():
    memories = get_memories()
    if not memories:
        speak("I don't remember anything yet.")
        return

    speak("Here's what I remember:")
    for memory in memories:
        speak(memory.content)

def search_memory_command(command):
    keyword = (command.replace("what do you remember about", "",).strip())

    print(f"Keyword: {keyword}")

    memories = search_memories(keyword)
    if not memories:
        speak(f"I don't remember anything about {keyword}.")
        return
    
    speak(f"Here's what I remember about {keyword}:")
    for memory in memories:
        speak(memory.content)

def forget_memory_command(command):
    keyword = (command.replace("forget", "",).strip())

    print(f"DELETE KEYWORD: {keyword}")

    deleted = delete_memory(keyword)

    if deleted:
        speak(f"I've forgotten that.")
    else:
        speak(f"I couldn't find that memory.")

def open_coding_workspace():

    speak("Initializing coding workspace.")

    subprocess.run(["code"], shell=True)

    webbrowser.open("https://github.com")

    webbrowser.open("https://chatgpt.com")

def open_aws_workspace():
    speak("Initializing AWS workspace.")

    webbrowser.open("https://console.aws.amazon.com")
    webbrowser.open("https://chatgpt.com")


def open_school_workspace():
    speak("Initializing school workspace.")

    webbrowser.open("https://canvas.fau.edu/")
    webbrowser.open("https://outlook.office.com/mail/?realm=fau.edu&vd=outlook")
    webbrowser.open("https://myfau.fau.edu/u/myfau/index")

def hello():
    speak("Hello Chandler")


def open_vscode():
    speak("Opening Visual Studio Code")
    subprocess.run(["code"], shell=True)


def current_time():
    now = datetime.now().strftime("%I:%M %p")
    speak(f"The current time is {now}")


def open_github():
    speak("Opening GitHub")
    webbrowser.open("https://github.com")


def open_chatgpt():
    speak("Opening ChatGPT")
    webbrowser.open("https://chatgpt.com")


def unknown():
    speak("Sorry, I don't know how to do that yet.")