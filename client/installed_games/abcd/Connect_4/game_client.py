import socket
import json
import threading
import sys
import os
import time

# Suppress pygame support prompt
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

# --- Networking Helper Functions ---
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
    except:
        return None

# --- Global State ---
state = {
    "board": [[0]*7 for _ in range(6)],
    "my_turn": False,
    "status_msg": "Connecting...",
    "running": True,
    "winner": None
}
state_lock = threading.Lock()

def network_listener(sock, player_name):
    """Listens for server messages in background."""
    global state
    while True:
        data = recv_json(sock)
        if not data:
            with state_lock:
                if state["running"]: 
                    state["status_msg"] = "Server Disconnected"
                    state["running"] = False
            break
        
        msg_type = data.get("type")
        
        with state_lock:
            if msg_type == "game_start":
                state["board"] = data["board"]
                state["status_msg"] = "Game Started!"
                
            elif msg_type == "turn_update":
                state["board"] = data["board"]
                state["my_turn"] = data["your_turn"]
                if state["my_turn"]:
                    state["status_msg"] = "YOUR TURN"
                else:
                    state["status_msg"] = f"{data['turn_player']}'s Turn"
                    
            elif msg_type == "game_over":
                state["board"] = data["board"]
                state["my_turn"] = False
                state["winner"] = data["winner"]

def run_game_client(server_ip: str, server_port: int, player_name: str):
    print(f"[Client] Connecting to {server_ip}:{server_port} as {player_name}")
    
    # 1. Socket Setup
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((server_ip, server_port))
    except Exception as e:
        print(f"[Client] Could not connect: {e}")
        return

    # 2. Handshake
    send_json(sock, {"type": "join", "username": player_name})
    resp = recv_json(sock)
    if not resp or resp.get("type") != "join_ack":
        print("[Client] Join Rejected.")
        sock.close()
        return

    my_id = resp["player_id"]
    print(f"[Client] Joined as Player {my_id}")

    # 3. Start Listener Thread
    t = threading.Thread(target=network_listener, args=(sock, player_name), daemon=True)
    t.start()

    # 4. Pygame GUI Setup
    pygame.init()
    
    SQUARESIZE = 100
    RADIUS = int(SQUARESIZE/2 - 5)
    width = 7 * SQUARESIZE
    height = (6 + 1) * SQUARESIZE 
    size = (width, height)
    
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption(f"Connect 4 - {player_name}")
    font = pygame.font.SysFont("monospace", 40)
    big_font = pygame.font.SysFont("monospace", 70, bold=True)
    
    BLUE = (0, 0, 255)
    BLACK = (0, 0, 0)
    RED = (255, 0, 0)
    YELLOW = (255, 255, 0)
    WHITE = (255, 255, 255)

    # 5. GUI Loop
    clock = pygame.time.Clock()
    game_over_timer_start = None
    
    while True:
        # A. Check State
        with state_lock:
            running = state["running"]
            winner = state["winner"]
            board_to_draw = state["board"]
            status_msg = state["status_msg"]
            my_turn = state["my_turn"]

        if not running and winner is None:
            print("[Client] Disconnected.")
            break

        # B. Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                send_json(sock, {"type": "game_end_ack"}) 
                sock.close()
                pygame.quit()
                return

            if event.type == pygame.MOUSEBUTTONDOWN:
                if my_turn and winner is None:
                    posx = event.pos[0]
                    col = int(posx // SQUARESIZE)
                    send_json(sock, {"type": "move", "col": col})
                    with state_lock:
                        state["my_turn"] = False

        # C. Drawing
        screen.fill(BLACK)
        
        # Draw Board
        for r in range(6):
            for c in range(7):
                pygame.draw.rect(screen, BLUE, (c*SQUARESIZE, (r+1)*SQUARESIZE, SQUARESIZE, SQUARESIZE))
                color = BLACK
                if board_to_draw[r][c] == 1:
                    color = RED
                elif board_to_draw[r][c] == 2:
                    color = YELLOW
                pygame.draw.circle(screen, color, 
                                   (int(c*SQUARESIZE + SQUARESIZE/2), int((r+1)*SQUARESIZE + SQUARESIZE/2)), 
                                   RADIUS)

        # Draw Status Text (Normal Game)
        if winner is None:
            text = font.render(status_msg, True, WHITE)
            screen.blit(text, (20, 20))

            # Draw Hover Piece
            if my_turn:
                posx, _ = pygame.mouse.get_pos()
                piece_color = RED if my_id == 1 else YELLOW
                pygame.draw.circle(screen, piece_color, (posx, int(SQUARESIZE/2)), RADIUS)

        # D. Game Over Handling (Overlay + White Text)
        if winner:
            # 1. Create a transparent overlay
            overlay = pygame.Surface((width, height))
            overlay.set_alpha(200)  # 0-255 transparency (200 is a nice dark dim)
            overlay.fill((0, 0, 0)) # Fill with black to create the gray/dim effect
            screen.blit(overlay, (0, 0))

            # 2. Determine Message
            if winner == player_name:
                msg = "YOU WON!"
            elif winner == "Draw":
                msg = "DRAW!"
            else:
                msg = "YOU LOST..."
            
            # 3. Render White Text
            res_text = big_font.render(msg, True, WHITE) # Forces White font
            
            # 4. Center the Text
            text_rect = res_text.get_rect(center=(width/2, height/2))
            screen.blit(res_text, text_rect)
            
            pygame.display.update()
            
            # 5. Timer for auto-close
            if game_over_timer_start is None:
                game_over_timer_start = time.time()
            
            if time.time() - game_over_timer_start > 3.0:
                print("[Client] Game finished. Sending ACK and closing.")
                send_json(sock, {"type": "game_end_ack"})
                with state_lock:
                    state["running"] = False
                break 

        pygame.display.update()
        clock.tick(30)

    # Cleanup
    sock.close()
    pygame.quit()