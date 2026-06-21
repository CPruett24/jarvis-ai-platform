import json

STATUS_FILE = "data/status.json"

def load_status():

    with open(STATUS_FILE, "r") as file:
        return json.load(file)


def save_status(data):

    with open(STATUS_FILE, "w") as file:
        json.dump(data, file, indent=4)

def update_status(status):

    data = load_status()

    data["status"] = status

    save_status(data)


def update_last_command(command):

    data = load_status()

    data["last_command"] = command

    save_status(data)


def update_last_response(response):

    data = load_status()

    data["last_response"] = response

    save_status(data)