import socket
import platform
import os
import sys
import threading
import time
import RecvSend
import base64
import subprocess
import json
from colorama import Fore, Style, init

# TODO :
# add double check on uploading
# add update game
# done

def print_error(message):
    print(f"{Fore.RED}{message}{Style.RESET_ALL}")

def print_ok(message):
    print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")

class DeveloperClient():
    def __init__(self):
        self.LOBBY_IP = "140.113.17.13" # 140.113.17.{11|12|13|14} (linux3 : 13)
        self.LOBBY_PORT = 20202
        self.USERNAME = None
        self.LOGGEDIN = False
        self.socket_lobby = None
        self.print_lock = threading.Lock()
        self.client_state = "LOGIN"
        self.running = False
        self.pending_list = []

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
        except (OSError, ConnectionResetError):
            print("[ERROR] Disconnected from the server...")
            self.exitGame()
        except Exception as e:
            print(f"[ERROR] Exception {e} @ receiver loop")
            self.running = False

        finally:
            self.running = False

    def messageHandler(self, msg):
        mtype = msg.get("type")
        if mtype == "command":
            if msg.get("msg") == "CLEAR_CLIENT":
                self.clearCLI()
            return

        if mtype == "state":
            state = msg.get("msg")
            # central dispatcher for state codes
            self.handle_state(state)
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
                #time.sleep(3)
            return

    def handle_state(self, state):
        with self.print_lock:
            if state == "SHOW_LOGIN_MENU":
                self.show_login_menu()
                
            elif state == "REGISTER_NAME":
                name = input("Choose a username: ").strip()
                RecvSend.sendJSON(self.socket_lobby, "response", name)
                
            elif state == "REGISTER_PASS":
                passwd = input("Choose a password: ").strip()
                RecvSend.sendJSON(self.socket_lobby, "response", passwd)
                
            elif state == "LOGIN_NAME":
                name = input("Enter username: ").strip()
                RecvSend.sendJSON(self.socket_lobby, "response", name)
                
            elif state == "LOGIN_PASS":
                passwd = input("Enter password: ").strip()
                RecvSend.sendJSON(self.socket_lobby, "response", passwd)
                
            elif state == "SHOW_LOBBY_MENU":
                self.show_lobby_menu()
                
            elif state == "UPLOAD_FLOW_START":
                # self.clearCLI()
                self.UploadGame()
            
            elif state == "UPDATE_FLOW_START":
                # print("Updating flow start.")
                # self.pending_list = RecvSend.recv_msg(self.socket_lobby).get("msg")
                # self.clearCLI()
                self.UpdateGame()
                
            elif state == "REQUEST_DELETE_GAME":
                # print("Entering delete game session.")
                # print(f"Updated pending list {self.pending_list}")
                # self.clearCLI()
                self.DeleteGame()
                
            else:
                print(f"[DEBUG] Unknown state from server: {state}")

    def handle_result(self, code, msg):
        with self.print_lock:
            if code == "REGISTER_OK":
                print_ok("Registration successful. You may login now.")
                
            elif code == "UPLOAD_SUCCESS":
                print_ok("Server: Upload successful.")
                
            elif code == "UPLOAD_FAILED":
                print_error("Server: Upload failed.")
                
            elif code == "UPDATE_SUCCESS":
                print_ok("Server: Update successful.")
                
            elif code == "UPDATE_FAILED":
                print_error("Server: Update failed.")
                
            elif code == "DELETE_OK":
                print_ok("Delete completed successfully.")
                
            elif code == "DELETE_CANCEL":
                print_ok("Delete cancelled.")
                
            elif code == "LOGOUT_OK":
                print_ok("Logged out!")
                
            elif code == "GOODBYE":
                print("Goodbye.")
                self.exitGame()
                
            else:
                print(f"[RESULT] {code}")
                
            # time.sleep(3.0)

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
                print_error("Upload failed...")
                
            elif code == "INVALID_ACTION":
                print_error("Invalid action.")
                
            else:
                print_error(f"[ERROR] {code}")
            
            # time.sleep(3.0)

    def show_login_menu(self):
        # self.clearCLI()
        print("\nWelcome to the developer mode!")
        print("1. Register Account")
        print("2. Login")
        print("3. Leave")
        ans = input("Please choose (1-3): ").strip()
        RecvSend.sendJSON(self.socket_lobby, "response", ans)

    def show_lobby_menu(self):
        # self.clearCLI()
        print("\nDeveloper Dashboard")
        print("1. Upload Game")
        print("2. Update Game")
        print("3. Delete Game")
        print("4. Create New Template")
        print("5. Logout")
        ans = input("Please choose (1-5): ").strip()
        if ans == "4":
            self.CreateTemplate()

        RecvSend.sendJSON(self.socket_lobby, "response", ans)
    
    def DeleteGame(self):
        print("\n")
        self.pending_list = RecvSend.recv_msg(self.socket_lobby).get("msg")
        
        length = len(self.pending_list)
        if length == 0:
            print_error("You don't have any uploaded games...")
            RecvSend.sendJSON(self.socket_lobby, "response", "ABORT")
            #time.sleep(3)
            return

        while True:
            self.ShowPendingList()
            print(f"{length + 1}. Cancel")
            ans = input(f"Please choose (1-{length + 1})\n").strip()
            if not ans.isdigit():
                print_error("Invalid Input")
                continue

            choice = int(ans)
            if choice == length + 1:
                print("Delete cancelled.")
                RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
                return
            
            if choice <= 0 or choice > len(self.pending_list):
                print_error("Invalid Input")
                continue
            
            while True:
                game_name = self.pending_list[choice-1].get("game_name")
                ans = input(f"Are you sure you want to delete the game: {game_name}? [y] / [n]\n")
                if ans != "y" and ans != "n":
                    print_error("Invalid Input")
                    continue
                else:
                    break
            if ans == "y":
                RecvSend.sendJSON(self.socket_lobby, "response", choice, game_name=game_name)
            else:
                RecvSend.sendJSON(self.socket_lobby, "response", "ABORT")
            break
        
    def ShowPendingList(self):
        for i in range(len(self.pending_list)):
            game_name = self.pending_list[i].get("game_name")
            print(f"{i + 1}. {game_name}")

    def CreateTemplate(self):
        game_name = ""
        while True:
            print("Please Enter your game name : ")
            game_name = input()
            print(f"Are you sure you want to name your game : {game_name}? ([y] / [n])")
            while True:
                ans = input()
                if ans != "y" and ans != "n":
                    print_error("Invalid input. Enter [y] or [n]")
                else:
                    break

            if ans == "n":
                continue
            else:
                break
        
        print(f"\n[INFO] Generating template for '{game_name}'...")

        try:
            subprocess.run(
                [sys.executable, "create_game_template.py", game_name], 
                check=True
            )
            print_ok("\nTemplate generated successfully!")
            print_ok(f"Please check the folder ./game/{game_name}, read the README.md first before developing!")
            input("Press enter to continue...")

        except subprocess.CalledProcessError as e:
            print_error(f"\n[ERROR] The template script failed with error code {e.returncode}.")
            input("Press enter to continue...")
        except FileNotFoundError:
            print_error("\n[ERROR] Could not find 'create_game_template.py'. Make sure it is in the same folder.")
            input("Press enter to continue...")
    
    def upload_file(self, sock, file_path, target_filename):
        if not os.path.exists(file_path):
            print_error(f"[ERROR] File not found: {file_path}")
            return False

        try:
            # 1. Read file as BINARY (rb)
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            # binary -> base64 str
            file_b64_str = base64.b64encode(file_bytes).decode('ascii')

            upload = {
                "fileName": target_filename,
                "content": file_b64_str
            }
            
            upload = json.dumps(upload)
            RecvSend.send_msg(sock, upload)
            
            print_ok(f"[UPLOAD] Sent {target_filename} ({len(file_bytes)} bytes)")
            return True
            
        except Exception as e:
            print_error(f"[ERROR] Failed to send {target_filename}: {e}")
            return False
    
    def GetGameFilePaths(self, full_game_path):
        config_path = os.path.join(full_game_path, "config.json")
        game_client_path = os.path.join(full_game_path, "game_client.py")
        game_server_path = os.path.join(full_game_path, "game_server.py")

        if not os.path.exists(config_path):
            print_error(f"[ERROR] Critical file missing: {config_path}")
            print_error( "        Please ensure your game folder structure is correct.")
            RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
            input("Press enter to continue...")
            return None, None, None
        
        if not os.path.exists(game_client_path):
            print_error(f"[ERROR] Critical file missing: {game_client_path}")
            print_error( "        Please ensure your game folder structure is correct.")
            RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
            input("Press enter to continue...")
            return None, None, None
        
        if not os.path.exists(game_server_path):
            print_error(f"[ERROR] Critical file missing: {game_server_path}")
            print_error( "        Please ensure your game folder structure is correct.")
            RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
            input("Press enter to continue...")
            return None, None, None

        return config_path, game_client_path, game_server_path
    
    def checkConfigData(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except json.JSONDecodeError:
            print_error(f"[ERROR] The provided config.json is not valid JSON.")
            RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
            #time.sleep(3)
            return None, False
        except Exception as e:
            print_error(f"[ERROR] Could not read config.json: {e}")
            RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
            #time.sleep(3)
            return None, False
        
        
        required_keys = ["game_name", "version", "description", "game_type", "max_players"]
        
        for key in required_keys:
            value = config_data.get(key)
            
            if value is None:
                print_error(f"[ERROR] Invalid config.json: Missing required field '{key}'.")
                RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
                input("Press enter to continue...")
                return None, False

            if isinstance(value, str) and not value.strip():
                print_error(f"[ERROR] Invalid config.json: Field '{key}' cannot be empty.")
                RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
                input("Press enter to continue...")
                return None, False
            
            if key == "max_players" and value < 2:
                print_error(f"[ERROR] Invalid config.json: Field '{key}' cannot be less than 2 players.")
                RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
                input("Press enter to continue...")
                return None, False
        
        return config_data, True
    
    def sendGameFiles(self, config_path, game_client_path, game_server_path) :
        files_to_send = [
            ("config.json", config_path),
            ("game_client.py", game_client_path),
            ("game_server.py", game_server_path),
        ]
        
        for filename, local_path in files_to_send:
            success = self.upload_file(self.socket_lobby, local_path, filename)
            if not success:
                print_error(f"[ABORT] Stopping upload due to error with {filename}")
                RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
                #time.sleep(3)
                return

        # print("[DEBUG] Fully sent required files.")
        RecvSend.sendJSON(self.socket_lobby, "action", "COMPLETE")
        return
    
    def UploadGame(self):
        games_root = "./games"
        if not os.path.exists(games_root):
            print_error(f"[ERROR] No 'games' folder found at {games_root}.")
            RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
            input("Press enter to continue...")
            return

        game_list = [d for d in os.listdir(games_root) if os.path.isdir(os.path.join(games_root, d))]

        if not game_list:
            print_error("[ERROR] You have no games in your workspace yet.")
            print_error("        Use the 'Create Template' option first.")
            RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
            input("Press enter to continue...")
            return

        print("\n=== Select a Game to Upload ===")
        for index, game in enumerate(game_list, 1):
            print(f"{index}. {game}")
        print(f"{len(game_list) + 1}. Cancel")

        selected_game = None
        while True:
            try:
                choice_str = input(f"Enter choice (1-{len(game_list) + 1}): ").strip()
                choice = int(choice_str)

                if choice == len(game_list) + 1:
                    print("Upload cancelled.")
                    RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
                    return
                
                if 1 <= choice <= len(game_list):
                    selected_game = game_list[choice - 1]
                    break
                else:
                    print_error(f"Invalid number. Please enter 1-{len(game_list) + 1}.")
            except ValueError:
                print_error("Invalid input. Please enter a number.")

        print(f"\n[INFO] Preparing to upload '{selected_game}'...")
        full_game_path = os.path.join(games_root, selected_game)
        
        config_path, game_client_path, game_server_path = self.GetGameFilePaths(full_game_path)
        if config_path is None:
            return

        config_data, passed = self.checkConfigData(config_path)
        
        if not passed:
            return

        print_ok(f"[OK] Config verified: {config_data['game_name']} (v{config_data['version']})")
        RecvSend.sendJSON(self.socket_lobby, "action", "GAME",
            game_name=config_data["game_name"],
            version=config_data["version"],
            max_players=config_data["max_players"])
        self.sendGameFiles(config_path, game_client_path, game_server_path)
        return

    def UpdateGame(self):
        self.pending_list = RecvSend.recv_msg(self.socket_lobby).get("msg")
        
        length = len(self.pending_list)
        if length == 0:
            print_error("You don't have any uploaded games...")
            RecvSend.sendJSON(self.socket_lobby, "response", "ABORT")
            #time.sleep(3)
            return

        while True:
            self.ShowPendingList()
            print(f"{length + 1}. Cancel")
            ans = input(f"Please choose (1-{length + 1})\n").strip()
            if not ans.isdigit():
                print_error("Invalid Input")
                continue
            choice = int(ans)
            
            if choice == length + 1:
                print("Update Cancel")
                RecvSend.sendJSON(self.socket_lobby, "response", "ABORT")
                return
            
            if choice <= 0 or choice > len(self.pending_list):
                print_error("Invalid Input")
                continue
            
            selected_game = self.pending_list[choice-1].get("game_name")
            print(f"Trying to update the game {selected_game}...")
            break
        
        games_root = "./games"
        full_game_path = os.path.join(games_root, selected_game)
        if not os.path.exists(full_game_path):
            print_error(f"[ERROR] The game folder: {full_game_path} is not found.")
            RecvSend.sendJSON(self.socket_lobby, "response", "ABORT")
            input("Press enter to continue...")
            return
        
        config_path, game_client_path, game_server_path = self.GetGameFilePaths(full_game_path)
        if config_path is None:
            return
        
        config_data, passed = self.checkConfigData(config_path)
        if not passed:
            return
        
        print_ok(f"[OK] Config verified: {config_data['game_name']} (v{config_data['version']})")
        
        old_version = self.pending_list[choice-1].get("version")
        new_version = config_data.get("version")
        passed = self.compareVersion(old_version, new_version)
        
        if not passed:
            print_error(f"The new version {new_version} must be greater than the old version {old_version}!")
            RecvSend.sendJSON(self.socket_lobby, "action", "ABORT")
            input("Press enter to continue...")
            return
        
        RecvSend.sendJSON(self.socket_lobby, "action", "GAME",
            game_name=config_data["game_name"],
            version=config_data["version"],
            max_players=config_data["max_players"])
        self.sendGameFiles(config_path, game_client_path, game_server_path)
        return
            
    def compareVersion(self, old_version, new_version):
        old_major, old_minor, old_patch= map(int, old_version.split("."))
        new_major, new_minor, new_patch = map(int, new_version.split("."))
        
        if new_major != old_major:
            return new_major > old_major
        if new_minor != old_minor:
            return new_minor > old_minor
        return new_patch > old_patch

    def exitGame(self, force=False):
        def cleanup(socket, force):
            if force:
                print_error("Force exiting")
                try:
                    time.sleep(1.0)
                except Exception:
                    pass
            try:
                socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                socket.close()
            except Exception:
                pass

        if self.socket_lobby:
            cleanup(self.socket_lobby, force)
            self.socket_lobby = None
            # print("Socket lobby cleaned up")
    
    def main(self):
        try:
            self.connectLobby()
        except Exception as e:
            print(f"Unable to connect to lobby: {e}")
            return

        try:
            recv_thread = threading.Thread(target=self.receiver_loop, daemon=True)
            recv_thread.start()

            while recv_thread.is_alive():
                time.sleep(0.2)
        except (KeyboardInterrupt, OSError, ConnectionResetError):
            self.exitGame(force=True)
        finally:
            self.running = False
            try:
                recv_thread.join(timeout=1.0)
            except Exception:
                pass

if __name__ == "__main__":
    client = DeveloperClient()
    client.main()