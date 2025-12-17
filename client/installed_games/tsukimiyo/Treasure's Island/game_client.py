import socket
import json
import pygame
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
    data = conn.recv(length)
    if not data:
        return None
    return json.loads(data.decode())

# --- Game client ---
def run_game_client(server_ip: str, server_port: int, player_info: str):
    print(f"[Client] Connecting to {server_ip}:{server_port} ...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, server_port))
    send_json(sock, {"type": "join", "username": player_info})
    resp = recv_json(sock)
    if not resp or resp.get("type") != "join_ack":
        print("[Client] Join failed.")
        sock.close()
        return
    print(f"[Client] Joined as {player_info}")

    pygame.init()
    screen = pygame.display.set_mode((480, 600))
    pygame.display.set_caption(f"Treasure Island - {player_info}")
    font_big = pygame.font.SysFont(None, 70)
    font = pygame.font.SysFont(None, 30)
    small_font = pygame.font.SysFont(None, 24)
    clock = pygame.time.Clock()

    grid_size = 3
    cell_size = 120
    margin = 15
    grid_left = 45   # <-- Centered horizontally
    grid_top = 30

    game_state = {
        "board": ["?"] * 9,
        "revealed": [False] * 9,
        "scores": {},
        "turn": "",
        "winner": None
    }

    stop_flag = threading.Event()

    def recv_thread():
        nonlocal game_state
        while not stop_flag.is_set():
            try:
                data = recv_json(sock)
                if not data:
                    break
                if data["type"] == "state":
                    game_state = data
                elif data["type"] == "error":
                    print("Server error:", data["msg"])
            except:
                break
        stop_flag.set()
        print("[Client] Disconnected from server.")

    threading.Thread(target=recv_thread, daemon=True).start()

    running = True
    end_time = None

    while running and not stop_flag.is_set():
        screen.fill((25, 50, 70))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and not game_state["winner"]:
                if game_state["turn"] == player_info:
                    mx, my = pygame.mouse.get_pos()
                    for i in range(9):
                        x = grid_left + (i % grid_size) * (cell_size + margin)
                        y = grid_top + (i // grid_size) * (cell_size + margin)
                        rect = pygame.Rect(x, y, cell_size, cell_size)
                        if rect.collidepoint(mx, my):
                            if not game_state["revealed"][i]:
                                send_json(sock, {"type": "dig", "cell": i})

        # Draw centered grid
        for i in range(9):
            x = grid_left + (i % grid_size) * (cell_size + margin)
            y = grid_top + (i // grid_size) * (cell_size + margin)
            rect = pygame.Rect(x, y, cell_size, cell_size)
            pygame.draw.rect(screen, (190, 190, 190), rect)
            pygame.draw.rect(screen, (0, 0, 0), rect, 2)

            val = game_state["board"][i]
            if game_state["revealed"][i] or game_state["winner"]:
                if val == "treasure":
                    txt, color = "T", (255, 200, 0)
                elif val == "trap":
                    txt, color = "X", (255, 80, 80)
                elif val == "empty":
                    txt, color = ".", (180, 180, 180)
                else:
                    txt, color = "?", (0, 0, 0)
                surf = font_big.render(txt, True, color)
                rect_text = surf.get_rect(center=(x + cell_size // 2, y + cell_size // 2))
                screen.blit(surf, rect_text)

        # Draw score section (moved slightly lower)
        base_y = 440
        score_block_height = 30
        total_height = len(game_state["scores"]) * score_block_height
        start_y = base_y + (80 - total_height) // 2

        for idx, (p, s) in enumerate(game_state["scores"].items()):
            color = (255, 255, 0) if p == game_state["turn"] else (220, 220, 220)
            label = small_font.render(f"{p}: {s}", True, color)
            rect = label.get_rect(center=(240, start_y + idx * score_block_height))
            screen.blit(label, rect)

        # Status message
        if game_state["winner"]:
            msg = f"Winner: {game_state['winner']}"
            if end_time is None:
                end_time = time.time()
        else:
            msg = f"Turn: {game_state['turn']}"

        label = font.render(msg, True, (255, 255, 255))
        rect = label.get_rect(center=(240, 570))
        screen.blit(label, rect)

        pygame.display.flip()
        clock.tick(30)

        # Exit gracefully after 5 seconds on win
        if end_time and time.time() - end_time > 5:
            running = False

    stop_flag.set()
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except:
        pass
    sock.close()
    pygame.quit()
    print("[Client] Game closed.")

