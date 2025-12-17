import socket
import json
import random

# Utility send/recv JSON
def send_json(conn, data):
    msg = json.dumps(data).encode()
    conn.sendall(len(msg).to_bytes(4, "big") + msg)

def recv_json(conn):
    length_bytes = conn.recv(4)
    if not length_bytes:
        return None
    length = int.from_bytes(length_bytes, "big")
    return json.loads(conn.recv(length).decode())

def roll_dice(num_dice=3):
    return [random.randint(1, 6) for _ in range(num_dice)]

def start_game_server(ip: str, port: int, player_list: list):
    print(f"[LiarDiceServer] Starting at {ip}:{port}")
    print(f"[LiarDiceServer] Players: {player_list}")

    assert len(player_list) == 2, "This game requires exactly 2 players!"

    # 1. Accept connections
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((ip, port))
    server_sock.listen(2)
    print("[Server] Waiting for 2 players...")

    # Prepare mapping of username → connection
    player_conns = {}
    while len(player_conns) < len(player_list):
        conn, addr = server_sock.accept()
        print(f"[Server] Player connected: {addr}")

        # Expect handshake message
        join_data = recv_json(conn)
        if not join_data or join_data.get("type") != "join":
            print("[Server] Invalid join attempt, closing connection.")
            conn.close()
            continue

        username = join_data.get("username")
        print(f"[Server] Player identified as: {username}")

        if username not in player_list:
            print(f"[Server] Unknown player: {username}, closing connection.")
            send_json(conn, {"type": "error", "msg": "Invalid username."})
            conn.close()
            continue

        if username in player_conns:
            print(f"[Server] Duplicate player {username}, closing connection.")
            conn.close()
            continue

        player_conns[username] = conn
        send_json(conn, {"type": "join_ack", "msg": "Welcome!"})

    # Order sockets according to player_list
    conns = [player_conns[name] for name in player_list]

    # 2. Assign 3 dice to each player
    player_dice = [roll_dice(3), roll_dice(3)]
    print(f"[Debug] Player 0 ({player_list[0]}) dice = {player_dice[0]}")
    print(f"[Debug] Player 1 ({player_list[1]}) dice = {player_dice[1]}")

    # Send each player's dice privately
    for idx, conn in enumerate(conns):
        send_json(conn, {"type": "your_die", "value": player_dice[idx]})

    current_claim = None  # (count, face)
    turn = 0  # Player 0 starts

    # 3. Game loop
    while True:
        active_conn = conns[turn]
        other_conn = conns[1 - turn]

        send_json(active_conn, {
            "type": "your_turn",
            "current_claim": current_claim
        })

        response = recv_json(active_conn)
        if not response:
            break

        if response["action"] == "raise":
            new_claim = response["claim"]
            current_claim = new_claim

            # Notify the other player
            send_json(other_conn, {
                "type": "opponent_raised",
                "claim": new_claim
            })

            turn = 1 - turn  # switch turn

        elif response["action"] == "call":
            if current_claim is None:
                send_json(active_conn, {"type": "error", "msg": "You must raise first!"})
                continue

            # Flatten all dice from both players
            all_dice = player_dice[0] + player_dice[1]
            total_face = sum(1 for d in all_dice if d == current_claim["face"])
            valid = total_face >= current_claim["count"]

            # If claim was valid, caller loses; otherwise, caller wins
            winner_idx = turn if not valid else (1 - turn)
            winner_name = player_list[winner_idx]

            # Notify both players
            for c in conns:
                send_json(c, {
                    "type": "game_over",
                    "dice": {
                        player_list[0]: player_dice[0],
                        player_list[1]: player_dice[1]
                    },
                    "winner": winner_name
                })
            print(f"[Server] Game over! Winner: {winner_name}")
            break

    for c in conns:
        c.close()
    server_sock.close()
    print("[Server] Game ended.")
