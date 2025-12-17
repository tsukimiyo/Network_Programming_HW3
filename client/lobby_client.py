import socket
import platform
import os
import threading
import time
import RecvSend
import base64
import shutil
import json
import stat
import importlib.util
from colorama import Fore, Style

# TODO :
# find bugs
# UX improvement (feedback + good time.sleep())

def print_error(message):
    print(f"{Fore.RED}{message}{Style.RESET_ALL}")

def print_ok(message):
    print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")

def set_rwx(path):
    if platform.system() == "Windows":
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
    else:
        os.chmod(path, 0o755)

def set_rx(path):
    if platform.system() == "Windows":
        os.chmod(path, stat.S_IREAD | stat.S_IEXEC)
    else:
        os.chmod(path, 0o555)

def force_delete(action, name, exc):
    os.chmod(name, stat.S_IWRITE)
    os.remove(name)

class PlayerClient():
    def __init__(self):
        self.LOBBY_IP = "140.113.17.13" # 140.113.17.{11|12|13|14} (linux3 : 13)
        self.LOBBY_PORT = 20205
        self.GAME_IP = None
        self.GAME_PORT = None
        
        self.USERNAME = None
        self.LOGGEDIN = False
        self.socket_lobby = None
        self.socket_game = None
        self.print_lock = threading.Lock()
        self.client_state = "LOGIN"
        self.running = False
        self.pending_list = []
        self.isRoomHost = None

    def connectLobby(self):
        self.socket_lobby = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_lobby.connect((self.LOBBY_IP, self.LOBBY_PORT))

    def clearCLI(self):
        if platform.system() == "Windows":
            os.system("cls")
        else:
            os.system("clear")

    def receiver_loop(self):
        self.running = True
        try:
            while self.running and self.socket_lobby:
                msg = RecvSend.recv_msg(self.socket_lobby)
                if msg is None:
                    with self.print_lock:
                        print("\n[Connection lost from server...]")
                    break
                self.messageHandler(msg)
                time.sleep(0.05)
        except Exception as e:
            print(f"[ERROR] Exception {e} @ receiver loop")
            self.running = False
            self.exitGame(force=True)
        finally:
            self.running = False

    def cli_input_loop(self):
        # print("cli input loop started")
        try:
            while (self.socket_lobby is not None) and (self.client_state != "TERMINATE"):
                
                ans = input().strip()
                
                if self.socket_lobby is None:
                    break
                
                time.sleep(0.05)
                if self.client_state == "SHOW_LOGIN_MENU":
                    RecvSend.sendJSON(self.socket_lobby, "response", ans)
                    
                elif self.client_state == "REGISTER_NAME" or self.client_state == "REGISTER_PASS" \
                    or self.client_state == "LOGIN_NAME" or self.client_state == "LOGIN_PASS":
                    RecvSend.sendJSON(self.socket_lobby, "response", ans)

                elif self.client_state == "SHOW_LOBBY_MENU":
                    self.handle_lobby_menu(ans)
                    
                elif self.client_state == "RATE_GAME_FLOW_START":
                    self.handle_rate_game_list(ans)
                    
                elif self.client_state == "WRITING_COMMENT":
                    self.handle_writing_comment(ans)
                
                elif self.client_state == "BROWSE_GAME_FLOW_START":
                    self.handle_browse_game(ans)
                
                elif self.client_state == "SHOW_GAME_DETAILS":
                    self.handle_show_game_details(ans)
                
                elif self.client_state == "SHOW_AVAILABLE_GAMES":
                    self.handle_show_available_game(ans)
                
                elif self.client_state == "VERIFY_UPDATE":
                    self.handle_verify_update(ans)
                
                elif self.client_state == "JOIN_CREATE_ROOM":
                    self.handle_join_create_room(ans)
                    
                elif self.client_state == "SHOW_ROOM_LIST":
                    self.handle_join_room_list(ans)
                
                elif self.client_state == "IN_ROOM":
                    # print("[DEBUG] IN ROOM!")
                    RecvSend.sendJSON(self.socket_lobby, "response", ans, state="IN_ROOM")
                    
                elif self.client_state == "GAME_START":
                    self.start_game()
                
        except (KeyboardInterrupt, EOFError):
            raise
        except Exception as e:
            with self.print_lock:
                print(f"[Input Loop Error: {e}]")
            self.exitGame(force=True)

    def start_game(self):
        print("[INFO] Starting game...")
        user_name = self.USERNAME
        game_name = self.pending_game_name
        base_path = f"./installed_games/{user_name}/{game_name}"
        run_client = self.load_run_game_client(base_path)
        run_client(self.GAME_IP, self.GAME_PORT, user_name)

        print("[GAME] Game has ended!")
        RecvSend.sendJSON(self.socket_lobby, "GAME_END", "GAME_END")

    def load_run_game_client(self, base_path):
        module_path = os.path.join(base_path, "game_client.py")

        spec = importlib.util.spec_from_file_location("game_client_dynamic", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run_game_client

    def messageHandler(self, msg):
        mtype = msg.get("type")
        if mtype == "command":
            if msg.get("msg") == "CLEAR_CLIENT":
                self.clearCLI()
            return

        if mtype == "state":
            state = msg.get("msg")
            # central dispatcher for state codes
            self.handle_state(state, msg)
            return

        if mtype == "result":
            # informational result (non-fatal)
            code = msg.get("msg")
            self.handle_result(code, msg)
            return

        if mtype == "error":
            code = msg.get("msg")
            self.handle_error(code, msg)
            return

        if mtype == "auth" and msg.get("msg") == "LOGIN_SUCCESS":
            self.USERNAME = msg.get("id")
            self.LOGGEDIN = True
            self.client_state = "IN_LOBBY"
            with self.print_lock:
                print_ok(f"Logged in as {self.USERNAME}!")
                # time.sleep(3)
            return
        
        if mtype == "room_info":
            print(msg.get("msg"))
            return

    def handle_state(self, state, msg):
        with self.print_lock:
            self.client_state = state
            # print(f"[DEBUG] New state : {state}")
            if state == "SHOW_LOGIN_MENU":
                self.show_login_menu()
                
            elif state == "REGISTER_NAME":
                print("Choose a username: ")
                # RecvSend.sendJSON(self.socket_lobby, "response", name)
                
            elif state == "REGISTER_PASS":
                print("Choose a password: ")
                # RecvSend.sendJSON(self.socket_lobby, "response", passwd)
                
            elif state == "LOGIN_NAME":
                print("Enter username: ")
                #RecvSend.sendJSON(self.socket_lobby, "response", name)
                
            elif state == "LOGIN_PASS":
                print("Enter password: ")
                #RecvSend.sendJSON(self.socket_lobby, "response", passwd)
                
            elif state == "SHOW_LOBBY_MENU":
                self.show_lobby_menu()
                
            elif state == "RATE_GAME_FLOW_START":
                self.RateGameList()
                
            elif state == "BROWSE_GAME_FLOW_START":
                self.BrowseGameLib()
                
            elif state == "SHOW_GAME_DETAILS":
                self.ShowGameDetails()
                
            elif state == "JOIN_CREATE_ROOM":
                self.JoinCreateRoom()
                
            elif state == "SHOW_ROOM_LIST":
                self.ShowRoomList()
                
            elif state == "DOWNLOAD_GAME":
                self.DownloadGame()
                
            elif state == "RATE_GAME_FLOW_START":
                self.DownloadGame()
                
            elif self.client_state == "WRITING_COMMENT":
                print("Please write your comment:")
                
            elif state == "SHOW_AVAILABLE_GAMES":
                self.ShowAvailableGame()
                
            elif state == "VERIFY_GAME_VERSION":
                self.VerifyGameVersion(before_game_start=False)
                
            elif state == "CHECK_BEFORE_GAME":
                if not self.isRoomHost:
                    print("[DEBUG] sent check version state to server")
                    RecvSend.sendJSON(self.socket_lobby, "state", "", state="CHECK_VERSION")
                self.VerifyGameVersion(before_game_start=True)
                
            elif state == "IN_ROOM":
                if msg.get("identity") == "HOST":
                    self.isRoomHost = True
                else:
                    self.isRoomHost = False
                self.RoomMenu()
                
            elif state == "ROOM_TERMINATED":
                self.isRoomHost = None
                RecvSend.sendJSON(self.socket_lobby, "LEAVE", "", state="ROOM_CLOSED")
                print_error("Returning to lobby...")
                # time.sleep(3)
                
            elif state == "GAME_START":
                self.GAME_IP = msg.get("ip")
                self.GAME_PORT = msg.get("port")
                # RecvSend.sendJSON(self.socket_lobby, "room", "", state="GAME_START")
                print_ok("[GAME] Game is starting! Press Enter to Start the Game!")
                if not self.isRoomHost:
                    RecvSend.sendJSON(self.socket_lobby, "room", "", state="GAME_START")
                    # print("[GAME] Game is starting! Press Enter to Start the Game!")
                
            # else:
            #     print(f"[DEBUG] Unknown state from server: {state}")

    def handle_result(self, code, msg):
        with self.print_lock:
            if code == "REGISTER_OK":
                print_ok("Registration successful. You may login now.")
                
            elif code == "LOGOUT_OK":
                print_ok("Logged out!")
                
            elif code == "GOODBYE":
                print("Goodbye.")
                self.exitGame()
            
            elif code == "ROOM_CREATED":
                print_ok("Room created!")
                
            else:
                print(f"[RESULT] {code}")
            # time.sleep(3)

    def handle_error(self, code, msg):
        with self.print_lock:
            if code == "NOT_REGISTERED":
                print_error("You are not registered. Please register an account first.")
                
            elif code == "WRONG_PASSWORD":
                print_error("Wrong password. Try again.")
                
            elif code == "ALREADY_ONLINE":
                print_error("That account is already logged in elsewhere.")
                
            elif code == "REGISTER_DUPLICATE":
                print_error("Username already exists. Choose another.")
            
            elif code == "UPLOAD_DUPLICATE":
                print_error("Game name already exists. Choose another.")
            
            elif code == "UPLOAD_FAILED":
                print_error("Upload failed.")
            
            elif code == "INVALID_ACTION":
                print_error("Invalid action.")
        
            else:
                print_error(f"[ERROR]: {code}")
            
            # time.sleep(3)

    def show_login_menu(self):
        # self.clearCLI()
        print("Welcome to the Game Store App!")
        print("1. Register Account")
        print("2. Login")
        print("3. Leave")
        print("Please choose (1-3): ")

    def show_lobby_menu(self):
        # self.clearCLI()
        print("\nGame Store Menu")
        print("1. Browse Game") # BROWSE + DOWNLOAD
        print("2. Rate Games") # ADD COMMENT + REVIEW HERE
        print("3. Delete Game") # DELETE GAME
        print("4. Play Game") # JOIN / CREATE ROOM
        print("5. Logout")
        print("Please choose (1-5): ")
        
    def handle_lobby_menu(self, ans):
        if ans == "3":
            self.DeleteGame()

        RecvSend.sendJSON(self.socket_lobby, "response", ans)
    
    def RateGameList(self):
        # self.clearCLI()
        print("\n")
        data = RecvSend.recv_msg(self.socket_lobby)
        game_list = data.get("game_list", {})
        if not game_list:
            print_error("You haven't played any games yet...")
            self.pending_game_list = []
            RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
            # time.sleep(3)
            return

        print("=== Game List ===")
        sorted_games = sorted(game_list.items(), key=lambda x: x[1], reverse=True)
        self.pending_game_list = sorted_games

        for idx, (game_name, play_count) in enumerate(sorted_games, start=1):
            print(f"{idx}. {game_name:<25} | Played {play_count} time(s)")

        cancel_index = len(sorted_games) + 1
        print(f"{cancel_index}. Cancel")
    
    def handle_rate_game_list(self, ans):
        if not ans.isdigit():
            print_error("Invalid Input, please input a number")
            return

        choice = int(ans)
        game_list = self.pending_game_list
        length = len(game_list)

        cancel_index = length + 1
        if choice == cancel_index:
            RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
            return

        if choice <= 0 or choice > length:
            print_error("Invalid Input")
            return

        selected_game = game_list[choice - 1][0]
        self.pending_game_name = selected_game
        RecvSend.sendJSON(self.socket_lobby, "response", selected_game)
    
    def handle_writing_comment(self, comment):
        print("Are you sure with your comment? ([y] / [n]) ")
        print(f"Your comment : {comment}")
        
        while True:
            ans = input()
            if ans != "y" and ans != "n":
                print_error("Invalid Answer")
            else:
                break
        
        if ans == "n":
            print("Please write your comment : ")
            return
        
        print("Please rate the game (1-5): ")
        while True:
            score = input()
            if not score.isdigit():
                print_error("Invalid Input, please input a number")
                continue
            
            score = int(score)
            if score < 1 or score > 5:
                print_error("Please enter a number between 1 to 5!")
                continue
            
            break
        
        RecvSend.sendJSON(self.socket_lobby, "rate", "", comment=comment, score=score)
    
    def BrowseGameLib(self):
        # self.clearCLI()
        game_list = self.pending_game_list = RecvSend.recv_msg(self.socket_lobby).get("game_list")
        print("\n")
        length = len(game_list)
        if not game_list:
            RecvSend.sendJSON(self.socket_lobby, "response", "BROWSE_ABORT")
            print_error("There are no games available right now...")
            return
        
        print("Choose a game to you want to know more about!")
        for i in range(len(game_list)):
            print(f"{i + 1}. {game_list[i]}")
        print(f"{length + 1}. Cancel")
        print(f"Please choose (1-{length + 1})")
    
    def handle_browse_game(self, ans):
        if not ans.isdigit():
            print_error("Invalid Input, please input a number")
            return
        game_list = self.pending_game_list
        length = len(game_list)
        
        choice = int(ans)
        if choice == length + 1:
            # print("Browse cancelled.")
            RecvSend.sendJSON(self.socket_lobby, "action", "BROWSE_ABORT")
            return
        
        if choice <= 0 or choice > length:
            print_error("Invalid Input")
            return

        self.pending_game_name = game_list[choice-1]
        print(f"Sending the game name : {self.pending_game_name}")
        RecvSend.sendJSON(self.socket_lobby, "response", "", game_name=self.pending_game_name)
    
    def ShowGameDetails(self):
        # self.clearCLI()
        print("\n")
        self.pending_game_data = RecvSend.recv_msg(self.socket_lobby).get("game_details")
        comments = RecvSend.recv_msg(self.socket_lobby).get("comments", [])

        print("="*50)
        print("Game Details".center(50))
        print("="*50)
        # Metadata
        keys_to_show = [
            "game_name", "owner", "version", "game_type",
            "max_players", "downloads", "upload_time", "rate"
        ]
        for key in keys_to_show:
            print(f"{key.replace('_',' ').title():15}: {self.pending_game_data.get(key, 'N/A')}")

        print("\nDescription:")
        print(self.pending_game_data.get("description", "No description available."))
        print("\n" + "-"*50)
        print("Comments".center(50))
        print("-"*50)

        if not comments:
            print("No comments yet.")
        else:
            page_size = 5
            start_index = len(comments) - page_size
            start_index = max(0, start_index)
            # show 5 latest comments
            batch = comments[start_index:]
            for entry in batch:
                username = entry.get("username", "Unknown")
                comment = entry.get("comment", "")
                score = entry.get("score", 0.0)

                print(f"\n{username}")
                print(f"Rating : {score}/5.0")
                print(f"Comment: {comment}")

        print("\nWhat would you like to do?")
        print("1. Download this game")
        print("2. Go back to game list")
        print("Choose (1/2): ")
        return
    
    def DeleteGame(self):
        # self.clearCLI()
        username = self.USERNAME

        base_dir = f"./installed_games/{username}"

        if not os.path.exists(base_dir):
            print_error("You don't have any installed games.")
            # time.sleep(3)
            return
        games = [
            d for d in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, d))
        ]

        if not games:
            print_error("You don't have any installed games.")
            # time.sleep(3)
            return

        print("\n=== Installed Games ===")
        for idx, g in enumerate(games, 1):
            print(f"{idx}. {g}")
        print("=======================\n")

        # Input selection
        while True:
            choice = input("Enter the number of the game to delete (or 'q' to cancel): ").strip()

            if choice.lower() == "q":
                # print("[DeleteGame] Cancelled.")
                return

            if not choice.isdigit():
                print_error("Invalid input. Enter a number.")
                continue

            choice = int(choice)
            if 1 <= choice <= len(games):
                game_to_delete = games[choice - 1]
                break
            else:
                print_error("Invalid input. Try again.")

        print(f"Are you sure you want to delete '{game_to_delete}'? (y/n): ")
        while True:
            ans = input().strip().lower()
            if ans == "n":
                # print("[INFO] Deletion cancelled.")
                return
            elif ans == "y":
                break
            else:
                print_error("Invalid Answer.")

        game_path = os.path.join(base_dir, game_to_delete)

        try:
            set_rwx(game_path)
            shutil.rmtree(game_path, onerror=force_delete)
            print_ok(f"[DeleteGame] Game '{game_to_delete}' deleted successfully.")
            # time.sleep(3)
        except Exception as e:
            print_error(f"[DeleteGame] ERROR: Failed to delete game. Reason: {e}")
            # time.sleep(3)

    def handle_show_game_details(self, ans):
        if ans == "1":
            RecvSend.sendJSON(self.socket_lobby, "DOWNLOAD", "", game_name=self.pending_game_data["game_name"])
            self.pending_game_name = self.pending_game_data["game_name"]
        elif ans == "2":
            RecvSend.sendJSON(self.socket_lobby, "RETURN", "")
        else:
            print_error("Invalid choice. Please enter 1 or 2.")

    def DownloadGame(self):
        try:
            files = {}
            game_name = self.pending_game_name
            print("[INFO] Starting to download game files...")
            while True:
                data = RecvSend.recv_msg(self.socket_lobby)

                if data.get("msg") == "COMPLETE":
                    print_ok("[OK] Game File Downloaded!")
                    break

                if data.get("msg") == "ABORT":
                    print_error(f"[ERROR] Can't download the game: {game_name}.")
                    r = data.get("reason")
                    print_error(f"[ERROR] Reason : {r}")
                    input("Press enter to continue...")
                    return

                if "fileName" in data and "content" in data:
                    filename = data["fileName"]
                    content = data["content"]
                    files[filename] = content
                    continue
            
            print("[INFO] Writing files to disk...")
            username = self.USERNAME
            game_roots = "./installed_games"
            game_user_dir = os.path.join(game_roots, username)
            game_dir = os.path.join(game_user_dir, game_name)
            
            os.makedirs(game_user_dir, exist_ok=True)
            set_rwx(game_user_dir)

            if os.path.exists(game_dir):
                set_rwx(game_dir)
                shutil.rmtree(game_dir, onerror=force_delete)

            os.makedirs(game_dir, exist_ok=True)
            set_rwx(game_dir)

            for filename, b64_content in files.items():
                try:
                    file_bytes = base64.b64decode(b64_content)
                except Exception as e:
                    print_error(f"Base64 decode failed for {filename}: {e}. Please try downloading again.")
                    shutil.rmtree(game_dir)
                    # time.sleep(3)
                    return

                save_path = os.path.join(game_dir, filename)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(file_bytes)
            
                set_rx(save_path)

            set_rx(game_dir)
            print_ok("[OK] Download Complete!")
            # time.sleep(3)
        except:
            raise
        
    def ShowAvailableGame(self):
        # self.clearCLI()
        data = RecvSend.recv_msg(self.socket_lobby)
        self.pending_game_list = data.get("game_list", [])
        game_list = self.pending_game_list

        if not game_list:
            print_error("There are currently no games available on the server.")
            RecvSend.sendJSON(self.socket_lobby, "ABORT", "ABORT")
            # time.sleep(3)
            return

        print("\n=== Available Games ===")
        for i, g in enumerate(game_list, 1):
            print(f"{i}. {g['game_name']}")
        print(f"{len(game_list)+1}. Back")
        print(f"Choose (1-{len(game_list)+1}): ")
    
    def handle_show_available_game(self, ans):
        if not ans.isdigit():
            print_error("Invalid Input")
            return
        
        choice = int(ans)
        length = len(self.pending_game_list)
        if choice == length + 1:
            RecvSend.sendJSON(self.socket_lobby, "ABORT", "ABORT")
            return
        if 1 <= choice <= length:
            self.pending_game_name = self.pending_game_list[choice - 1]["game_name"]
            RecvSend.sendJSON(self.socket_lobby, "selected_game", self.pending_game_name)
        else:
            print("Invalid choice.")
            return
    
    def VerifyGameVersion(self, before_game_start=False):
        print(f"[INFO] Checking game : {self.pending_game_name}'s version and files...")
        latest_version = RecvSend.recv_msg(self.socket_lobby).get("version")
        if latest_version is None:
            print_error(f"[ERROR] Game is deleted by the developer...")
            # time.sleep(3)
            return
        
        is_installed = self.check_file_and_version(self.pending_game_name, latest_version)

        if is_installed:
            RecvSend.sendJSON(self.socket_lobby, "status", "", status="PASS")
            print_ok(f"[INFO] Version check ok!")

        elif not before_game_start and not is_installed: # menu stage
            self.client_state = "VERIFY_UPDATE"
            print_error("\n[WARNING] Local installation of this game is missing or outdated.")
            print_error("\nYou must download/update the game before playing.")
            print("Download now? (y/n): ")
        
        # speical case : check right before game start
        elif before_game_start and not is_installed:
            RecvSend.sendJSON(self.socket_lobby, "status", "", status="DOWNLOAD")
            print("\n[INFO] Found newer version. Auto updating...")
            self.DownloadGame()
            
    def handle_verify_update(self, ans):
        if ans == "y":
            RecvSend.sendJSON(self.socket_lobby, "status", "", status="DOWNLOAD")
        elif ans == "n":
            RecvSend.sendJSON(self.socket_lobby, "status", "", status="ABORT")
        else:
            print_error("Invalid input. Please enter 'y' or 'n'.")
    
    def JoinCreateRoom(self):
        # self.clearCLI()
        print(f"\n=== {self.pending_game_name} Ready to Play ===")
        print("1. Join Room")
        print("2. Create Room")
        print("3. Back")
        print("Choose (1-3): ")
        
    def handle_join_create_room(self, ans):
        if ans == "1":
            RecvSend.sendJSON(self.socket_lobby, "action", "", action="JOIN_ROOM")
        elif ans == "2":
            RecvSend.sendJSON(self.socket_lobby, "action", "", action="CREATE_ROOM")
        elif ans == "3":
            RecvSend.sendJSON(self.socket_lobby, "action", "", action="BACK")
        else:
            print_error("Invalid choice.")
    
    def ShowRoomList(self):
        # self.clearCLI()
        room_list = self.pending_room_list = RecvSend.recv_msg(self.socket_lobby).get("room_list")
        if len(room_list) == 0:
            RecvSend.sendJSON(self.socket_lobby, "ABORT", "ABORT")
            print_error("No available rooms!")
            # time.sleep(3)
            return
        print("\n============================================")
        for idx, room in enumerate(room_list, 1):
            host = room["hostName"]
            curr = len(room["players"])
            maxp = room["max_players"]
            remain = maxp - curr
            
            print(f"{idx}. Host: {host} | Players: {curr}/{maxp} | Slots Left: {remain}")

        print(f"{len(room_list) + 1}. Cancel / Back")
        print("============================================")
        print("Choose a room to join:")
        
    def handle_join_room_list(self, ans):
        if not ans.isdigit():
            print_error("Invalid Input")
            return
        
        choice = int(ans)
        length = len(self.pending_room_list)
        if choice == length + 1:
            RecvSend.sendJSON(self.socket_lobby, "ABORT", "ABORT")
            return
        if 1 <= choice <= length:
            hostName = self.pending_room_list[choice - 1]["hostName"]
            RecvSend.sendJSON(self.socket_lobby, "selected_room", hostName)
        else:
            print_error("Invalid choice.")
            return
    
    def RoomMenu(self):
        if self.isRoomHost:
            print("Type /start to start the game, /leave to leave the room")
        else:
            print("Type /leave to leave the room. (waiting for host to start)")

    def check_file_and_version(self, game_name, latest_version):
        game_root = "./installed_games"
        game_user_dir = os.path.join(game_root, self.USERNAME)
        game_dir = os.path.join(game_user_dir, game_name)

        config_path = os.path.join(game_dir, "config.json")
        client_path = os.path.join(game_dir, "game_client.py")

        installed_ok = True
        installed_version = None

        # Check folder exists
        if not os.path.isdir(game_dir):
            installed_ok = False

        # Check config.json exists and valid
        elif not os.path.exists(config_path):
            installed_ok = False
        else:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                installed_version = config_data.get("version")
            except Exception:
                installed_ok = False

        # Check required script exists
        if installed_ok and not os.path.exists(client_path):
            installed_ok = False

        if installed_ok and installed_version != latest_version:
            installed_ok = False
            
        return installed_ok

    def exitGame(self, force=False):
        def cleanup(socket):
            try:
                socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                socket.close()
            except Exception:
                pass
        
        if force and self.client_state == "IN_ROOM":
            RecvSend.sendJSON(self.socket_lobby, "")
        
        if self.socket_lobby:
            cleanup(self.socket_lobby)
            self.socket_lobby = None
        if not force:
            print("Press enter to exit...")
    
    def main(self):
        try:
            self.connectLobby()
        except Exception as e:
            print_error(f"Unable to connect to lobby: {e}")
            return

        try:
            recv_thread = threading.Thread(target=self.receiver_loop, daemon=True)
            recv_thread.start()

            self.cli_input_loop()
        except (KeyboardInterrupt, OSError, ConnectionResetError):
            self.exitGame(force=True)
        finally:
            self.running = False
            try:
                recv_thread.join(timeout=1.0)
            except Exception:
                pass

if __name__ == "__main__":
    client = PlayerClient()
    client.main()