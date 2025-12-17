import socket
import json

def send_json(conn, data):
    msg = json.dumps(data).encode()
    conn.sendall(len(msg).to_bytes(4, "big") + msg)

def recv_json(conn):
    length_bytes = conn.recv(4)
    if not length_bytes:
        return None
    length = int.from_bytes(length_bytes, "big")
    return json.loads(conn.recv(length).decode())

def run_game_client(server_ip: str, server_port: int, player_info: str):
    print(f"[Client] Connecting to {server_ip}:{server_port} ...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, server_port))
    print("[Client] Connected!")

    # --- Send join handshake ---
    send_json(sock, {"type": "join", "username": player_info})
    resp = recv_json(sock)
    if not resp or resp.get("type") != "join_ack":
        print("[Client] Join failed! Disconnecting.")
        sock.close()
        return
    print(f"[Client] Joined as {player_info}")

    my_dice = []

    while True:
        data = recv_json(sock)
        if not data:
            break

        t = data["type"]

        if t == "your_die":
            my_dice = data["value"]
            print(f"[Game] Your dice: {my_dice}")

        elif t == "your_turn":
            print("\n=== Your Turn ===")
            claim = data["current_claim"]
            if claim:
                print(f"Current claim: at least {claim['count']} of face {claim['face']}")
            else:
                print("No claim yet.")

            while True:
                action = input("Choose action [raise/call]: ").strip()
                if action in ("raise", "call"):
                    break

            if action == "raise":
                count = int(input("Enter count: "))
                face = int(input("Enter face (1-6): "))
                send_json(sock, {
                    "action": "raise",
                    "claim": {"count": count, "face": face}
                })
            else:
                send_json(sock, {"action": "call"})

        elif t == "opponent_raised":
            claim = data["claim"]
            print(f"\n[Opponent] Raised to: at least {claim['count']} of face {claim['face']}")

        elif t == "game_over":
            dice = data["dice"]
            winner = data["winner"]

            print("\n=== GAME OVER ===")
            print("Final dice:")
            for player, dlist in dice.items():
                print(f"  {player}: {dlist}")

            if winner == player_info:
                print("\n🎉 YOU WIN!")
            else:
                print(f"\nYou lose! Winner was {winner}.")
            break
        
        elif t == "error":
            print(f"Error: {data['msg']}")

    sock.close()
    print("[Client] Disconnected.")
