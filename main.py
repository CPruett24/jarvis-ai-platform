from commands.router import process

while True:
    command = input("You: ")

    if command.lower() == "exit":
        print("Shutting down.")
        break

    process(command)