import socket
import json
import select
import time

def send_json(conn, data):
    msg = json.dumps(data).encode()
    try:
        conn.sendall(len(msg).to_bytes(4, "big") + msg)
    except OSError:
        pass

def recv_json(conn):
    try:
        length_bytes = conn.recv(4)
        if not length_bytes:
            return None
        length = int.from_bytes(length_bytes, "big")
        return json.loads(conn.recv(length).decode())
    except (OSError, ValueError):
        return None

# --- Game Logic Constants ---
ROWS = 6
COLS = 7

def check_win(board, piece):
    # Check horizontal
    for c in range(COLS - 3):
        for r in range(ROWS):
            if board[r][c] == piece and board[r][c+1] == piece and board[r][c+2] == piece and board[r][c+3] == piece:
                return True
    # Check vertical
    for c in range(COLS):
        for r in range(ROWS - 3):
            if board[r][c] == piece and board[r+1][c] == piece and board[r+2][c] == piece and board[r+3][c] == piece:
                return True
    # Check diagonals
    for c in range(COLS - 3):
        for r in range(ROWS - 3):
            if board[r][c] == piece and board[r+1][c+1] == piece and board[r+2][c+2] == piece and board[r+3][c+3] == piece:
                return True
    for c in range(COLS - 3):
        for r in range(3, ROWS):
            if board[r][c] == piece and board[r-1][c+1] == piece and board[r-2][c+2] == piece and board[r-3][c+3] == piece:
                return True
    return False

def start_game_server(ip: str, port: int, player_list: list):
    print(f"[C4Server] Starting at {ip}:{port}")
    
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((ip, port))
    server_sock.listen(2)

    connected_players = {}
    
    # 1. Accept Connections
    while len(connected_players) < 2:
        conn, addr = server_sock.accept()
        req = recv_json(conn)
        if not req or req.get("type") != "join":
            conn.close()
            continue
        username = req.get("username")
        if username not in player_list or username in connected_players:
            conn.close()
            continue
        pid = len(connected_players) + 1
        connected_players[username] = {"conn": conn, "id": pid}
        send_json(conn, {"type": "join_ack", "player_id": pid})
        print(f"[Server] {username} joined.")

    # Sort connections by ID
    p1_name = next(n for n, p in connected_players.items() if p["id"] == 1)
    p2_name = next(n for n, p in connected_players.items() if p["id"] == 2)
    p1_conn = connected_players[p1_name]["conn"]
    p2_conn = connected_players[p2_name]["conn"]
    
    # 2. Game Loop
    board = [[0]*COLS for _ in range(ROWS)]
    turn_id = 1
    running = True
    
    start_msg = {"type": "game_start", "board": board, "p1": p1_name, "p2": p2_name}
    send_json(p1_conn, start_msg)
    send_json(p2_conn, start_msg)

    while running:
        current_name = p1_name if turn_id == 1 else p2_name
        current_conn = p1_conn if turn_id == 1 else p2_conn
        other_conn = p2_conn if turn_id == 1 else p1_conn
        
        # Broadcast Turn
        update = {"type": "turn_update", "board": board, "your_turn": False, "turn_player": current_name}
        send_json(other_conn, update)
        update["your_turn"] = True
        send_json(current_conn, update)
        
        # Receive Move
        move = recv_json(current_conn)
        if not move: 
            break # Disconnection

        if move.get("type") == "move":
            col = move.get("col")
            if 0 <= col < COLS and board[0][col] == 0:
                # Apply Move
                for r in range(ROWS-1, -1, -1):
                    if board[r][col] == 0:
                        board[r][col] = turn_id
                        break
                
                # Check Win
                winner = None
                if check_win(board, turn_id):
                    winner = current_name
                elif all(board[0][c] != 0 for c in range(COLS)):
                    winner = "Draw"
                
                if winner:
                    end_msg = {"type": "game_over", "board": board, "winner": winner}
                    send_json(p1_conn, end_msg)
                    send_json(p2_conn, end_msg)
                    running = False # End main loop
                else:
                    turn_id = 3 - turn_id # Switch

    # 3. Game Over / Cleanup Phase
    print("[Server] Game Over. Waiting for clients to acknowledge...")
    
    # We wait for both clients to send "game_end_ack" or close the socket.
    # We use select() to handle them simultaneously.
    inputs = [p1_conn, p2_conn]
    start_wait = time.time()
    
    while inputs and (time.time() - start_wait < 10): # 10 second timeout
        readable, _, _ = select.select(inputs, [], [], 1.0)
        for s in readable:
            try:
                data = recv_json(s)
                # If they send ACK or disconnect (data is None), we consider them done
                if not data or data.get("type") == "game_end_ack":
                    inputs.remove(s)
                    s.close()
            except:
                if s in inputs: inputs.remove(s)
                s.close()

    print("[Server] Closing server.")
    for s in inputs: s.close() # Close remaining
    server_sock.close()