from services.ai_service import detect_intent

while True:

    command = input("Command: ")

    intent = detect_intent(command)

    print(intent)