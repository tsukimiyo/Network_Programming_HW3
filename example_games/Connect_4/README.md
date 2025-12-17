# Connect_4

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
    "game_name": "Connect_4",
    "version": "1.0.0",
    "description": "",
    "game_type": "", // or "GUI"
    "max_players": None
}
Update version whenever you publish a new version.

4. Folder structure
games/
  └── Connect_4/
        ├── game_server.py
        ├── game_client.py
        ├── config.json
        ├── README.md
✔ You may now implement your game inside this folder.

Good luck!
