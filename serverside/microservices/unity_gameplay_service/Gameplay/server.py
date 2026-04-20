from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import threading
import time

app = Flask(__name__)
CORS(app)

FILE_PATH = "gameState.json"
CONFIG_PATH = "config.json"

# 🔹 Load config
def load_config():
    if not os.path.exists(CONFIG_PATH):
        default = {
            "resetDelay": 5,
            "resetOnStart": True
        }
        with open(CONFIG_PATH, 'w') as f:
            json.dump(default, f, indent=4)
        return default

    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

config = load_config()

# 🔹 Ensure state file exists
def init_file():
    if config.get("resetOnStart", True):
        data = {
            "allPlayersFinished": False,
            "gameStartTime": time.time()
        }
        with open(FILE_PATH, 'w') as f:
            json.dump(data, f, indent=4)
        print("🟢 Reset on start enabled")
    else:
        if not os.path.exists(FILE_PATH):
            data = {
                "allPlayersFinished": False,
                "gameStartTime": time.time()
            }
            with open(FILE_PATH, 'w') as f:
                json.dump(data, f, indent=4)

init_file()

# 🔹 Helper: Load state
def load_state():
    if not os.path.exists(FILE_PATH):
        return {
            "allPlayersFinished": False,
            "gameStartTime": time.time()
        }

    with open(FILE_PATH, 'r') as f:
        return json.load(f)

# 🔹 Helper: Save state
def save_state(data):
    with open(FILE_PATH, 'w') as f:
        json.dump(data, f, indent=4)

# 🔹 Reset logic (used when game finishes)
def reset_state_after_delay():
    delay = config.get("resetDelay", 5)
    time.sleep(delay)

    data = {
        "allPlayersFinished": False,
        "gameStartTime": time.time()
    }

    save_state(data)

    print(f"🔄 Game restarted after {delay} seconds")

# 🔹 Save endpoint (called by your game logic)
@app.route('/save', methods=['POST'])
def save():
    data = request.json

    current_state = load_state()
    current_state.update(data)

    save_state(current_state)

    print("🔥 Received:", data)

    # If game finished → trigger restart
    if current_state.get("allPlayersFinished") is True:
        threading.Thread(target=reset_state_after_delay).start()

    return jsonify({"status": "saved", "data": current_state})

# 🔹 Load endpoint (legacy support)
@app.route('/load', methods=['GET'])
def load():
    return jsonify(load_state())

# 🔹 Server time (for sync)
@app.route('/time', methods=['GET'])
def get_time():
    return jsonify({
        "serverTime": time.time()
    })

# 🔹 Game state (includes start time)
@app.route('/state', methods=['GET'])
def get_state():
    return jsonify(load_state())

# 🔹 Combined sync (BEST endpoint to use)
@app.route('/sync', methods=['GET'])
def sync():
    state = load_state()

    return jsonify({
        "serverTime": time.time(),
        "gameStartTime": state["gameStartTime"],
        "allPlayersFinished": state.get("allPlayersFinished", False)
    })

# 🔹 Manual restart
@app.route('/restart', methods=['POST'])
def restart_game():
    data = {
        "allPlayersFinished": False,
        "gameStartTime": time.time()
    }

    save_state(data)

    return jsonify({"status": "restarted"})

# 🔹 Run server
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)