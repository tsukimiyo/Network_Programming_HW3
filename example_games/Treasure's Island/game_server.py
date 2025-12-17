import socket
import json
import random
import threading
import time

# Utility helpers
def send_json(conn, data):
    msg = json.dumps(data).encode()
    conn.sendall(len(msg).to_bytes(4, "big") + msg)

def recv_json(conn):
    length_bytes = conn.recv(4)
    if not length_bytes:
        return None
    length = int.from_bytes(length_bytes, "big")
    return json.loads(conn.recv(length).decode())

# --- Game logic ---
def create_board():
    cells = ["treasure"] * 5 + ["trap"] * 2 + ["empty"] * 2
    random.shuffle(cells)
    return cells

def start_game_server(ip: str, port: int, player_list: list):
    print(f"[TreasureIslandServer] Starting at {ip}:{port}")
    assert len(player_list) == 3, "This game requires exactly 3 players!"

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((ip, port))
    server_sock.listen(3)
    print("[Server] Waiting for 3 players...")

    player_conns = {}
    while len(player_conns) < len(player_list):
        conn, addr = server_sock.accept()
        print(f"[Server] Player connected from {addr}")

        join_data = recv_json(conn)
        if not join_data or join_data.get("type") != "join":
            conn.close()
            continue

        username = join_data.get("username")
        if username not in player_list or username in player_conns:
            send_json(conn, {"type": "error", "msg": "Invalid or duplicate username"})
            conn.close()
            continue

        player_conns[username] = conn
        send_json(conn, {"type": "join_ack"})
        print(f"[Server] {username} joined!")

    conns = [player_conns[name] for name in player_list]

    # Initialize game
    board = create_board()
    revealed = [False] * 9
    scores = {p: 0 for p in player_list}
    turn_index = 0
    winner = None

    def broadcast_state():
        for c in conns:
            send_json(c, {
                "type": "state",
                "board": board if winner else ["?" if not r else b for r, b in zip(revealed, board)],
                "revealed": revealed,
                "scores": scores,
                "turn": player_list[turn_index],
                "winner": winner
            })

    # Game loop
    while True:
        broadcast_state()
        current_player = player_list[turn_index]
        conn = player_conns[current_player]

        data = recv_json(conn)
        if not data:
            print(f"[Server] {current_player} disconnected!")
            break

        if data.get("type") != "dig":
            send_json(conn, {"type": "error", "msg": "Invalid action"})
            continue

        cell = data.get("cell")
        if not (0 <= cell < 9) or revealed[cell]:
            send_json(conn, {"type": "error", "msg": "Invalid cell"})
            continue

        revealed[cell] = True
        tile = board[cell]

        if tile == "treasure":
            scores[current_player] += 1
        elif tile == "trap":
            scores[current_player] -= 1

        if all(revealed):
            # Game over
            max_score = max(scores.values())
            winners = [p for p, s in scores.items() if s == max_score]
            winner = ", ".join(winners)
            broadcast_state()
            print(f"[Server] Game over! Winner(s): {winner}")
            time.sleep(3)
            break

        turn_index = (turn_index + 1) % 3

    for c in conns:
        try:
            c.shutdown(socket.SHUT_RDWR)
            c.close()
        except:
            pass
    server_sock.close()
    print("[Server] Game ended.")
