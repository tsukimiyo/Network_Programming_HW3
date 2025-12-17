#!/usr/bin/env python3
import os
import sys
import json

# -------------------------------------------------------------
# Content templates
# -------------------------------------------------------------

README_TEMPLATE = """# {game_name}

This game project was generated using the HW3 Game Template Generator.

Your game MUST follow these standardized rules so the Lobby Server and Lobby Client
can correctly launch, manage, and connect players to your game.

---

# 📌 Required Files

## 1. game_server.py
This file MUST provide the following function:

```python
def start_game_server(ip: str, port: int, room_info: dict):
    '''
    Called by Lobby Server after a room is created and enough players join.

    Parameters:
      ip (str): IP address to bind the game server.
      port (int): Port to bind the game server.
      room_info (dict):
          {
            "room_id": int,
            "players": [
                {"username": str},
                ...
            ]
          }

    Your responsibilities:
      - Open a TCP server at (ip, port)
      - Accept connections from all players
      - Manage the game state
      - Send/receive messages
      - Close all sockets when the game ends
    '''
    pass
You MUST NOT rename this function.
Lobby Server will dynamically import and call it.

2. game_client.py

This file MUST provide:
def run_game_client(server_ip: str, server_port: int, player_info: dict):
    '''
    Called by Lobby Client once the game server is ready.

    Parameters:
      server_ip (str)
      server_port (int)
      player_info (dict):
          {
            "player_id": str,
            "username": str
          }

    Your responsibilities:
      - Connect to game server
      - Handle input (CLI or GUI)
      - Display game state
      - Send player actions to the server
      - Cleanly exit when game ends
    '''
    pass
Do not rename this function — Lobby Client will import and execute it automatically.

3. config.json

Metadata needed by the Store and Lobby:
{
    "game_name": "{game_name}",
    "version": "1.0.0",
    "description": "",
    "game_type": "", // or "GUI"
    "max_players": None
}
Update version whenever you publish a new version.

4. Folder structure
games/
  └── {game_name}/
        ├── game_server.py
        ├── game_client.py
        ├── config.json
        ├── README.md
✔ You may now implement your game inside this folder.

Good luck!
"""

GAME_SERVER_TEMPLATE = '''"""
game_server.py

This server script is launched by the LOBBY SERVER after a room starts.
You MUST implement start_game_server(), which will:

bind to the given IP/port

accept client connections

run your game logic

send/receive game updates

close connections when finished
"""

def start_game_server(ip: str, port: int, player_list: list):
    """
    REQUIRED FUNCTION.
    The Lobby Server will dynamically import and call this function.

    Parameters:
        ip (str): IP address to bind
        port (int): Port number
        player_list (list): Player names
    """
    print(f"[GameServer] Starting at {ip}:{port}")
    print(f"[GameServer] Players: {player_list}")

# TODO: developer implements:
#   - socket setup
#   - game loop
#   - broadcast updates
#   - graceful shutdown
pass
'''

GAME_CLIENT_TEMPLATE = '''"""
game_client.py

This client script is launched by the LOBBY CLIENT when entering the game.
You MUST implement run_game_client(), which will:

connect to the game server

perform handshakes

process user input (CLI/GUI)

receive updates

render the game state
"""

def run_game_client(server_ip: str, server_port: int, player_name: str):
    """
    REQUIRED FUNCTION.
    The Lobby Client will dynamically import and call this function.

    Parameters:
        server_ip (str)
        server_port (int)
        player_name (str)
    """
    print(f"[GameClient] Connecting to {server_ip}:{server_port}")
    print(f"[GameClient] Player: {player_name}")

# TODO: developer implements:
#   - socket connect
#   - input loop
#   - communication with server
#   - render UI / print CLI output
pass
'''


def main():
    if len(sys.argv) != 2:
        print("Usage: python create_game_template.py <game_name>")
        sys.exit(1)

    # FIX IS HERE: Un-indent this line so it runs when arguments ARE correct
    game_name = sys.argv[1].strip()

    if not game_name:
        print("Error: game_name cannot be empty")
        sys.exit(1)

    games_root = "./games"
    game_dir = os.path.join(games_root, game_name)

    # Create ./games if needed
    if not os.path.exists(games_root):
        os.makedirs(games_root)
        print(f"[OK] Created folder: {games_root}")

    # Check if game already exists
    if os.path.exists(game_dir):
        print(f"[Error] Game '{game_name}' already exists at {game_dir}")
        sys.exit(1)

    # Create game directory
    os.makedirs(game_dir)
    print(f"[OK] Created game folder: {game_dir}")

    # Write config.json
    config_data = {
        "game_name": game_name,
        "version": "1.0.0",
        "description": "A short description of your game.",
        "game_type": "CLI",
        "max_players": 2
    }

    # Write config.json
    with open(os.path.join(game_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4)
    print("[OK] config.json created.")

    # Write README.md
    with open(os.path.join(game_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(README_TEMPLATE.replace("{game_name}", game_name))
    print("[OK] README.md created.")

    # Write game_server.py
    with open(os.path.join(game_dir, "game_server.py"), "w", encoding="utf-8") as f:
        f.write(GAME_SERVER_TEMPLATE)
    print("[OK] game_server.py created.")

    # Write game_client.py
    with open(os.path.join(game_dir, "game_client.py"), "w", encoding="utf-8") as f:
        f.write(GAME_CLIENT_TEMPLATE)
    print("[OK] game_client.py created.")

    print("\nTemplate creation complete!")
    print(f"Your new game is located at: {game_dir}")
    
if __name__ == "__main__":
    main()