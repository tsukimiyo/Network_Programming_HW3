import socket
import RecvSend
import threading
import json
import sys
import os
import base64
import importlib.util

class LobbyServer():
    def __init__(self):
        self.HOST = "140.113.17.13" # 140.113.17.{11|12|13|14} (linux3 : 13)
        self.PORT = 20205
        self.DBIP = "140.113.17.13"
        self.DBPORT = 20850
        self.DB_socket = None
        self.online_users = {}
        
        self.db_sock_lock = threading.Lock()
        
        self.room_locks = {} # dict: hostName → threading.Lock()
        self.global_lock = threading.Lock()
        
        self.port_lock = threading.Lock()
        self.used_ports = set()

    def connDB(self):
        self.DB_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.DB_socket.connect((self.DBIP, self.DBPORT))
        RecvSend.sendJSON(self.DB_socket, "AUTH", "", identity="LOBBY")

    def queryDB(self, collection: str, action: str, data):
        with self.db_sock_lock:
            payload = {
                "collection": collection,
                "action": action,
                "data": data
            }
            RecvSend.send_msg(self.DB_socket, json.dumps(payload))
            #print("[DEBUG] Request sent to DB server.")
            #print("[DEBUG] Waiting for response from DB server...")
            data = RecvSend.recv_msg(self.DB_socket)
        #print("[DEBUG] DB responded!")
        return data

    def message_action_or_response(self, msg):
        if msg is None:
            return None
        return msg.get("msg")

    def register(self, conn):
        RecvSend.sendJSON(conn, "state", "REGISTER_NAME")
        name_msg = RecvSend.recv_msg(conn)
        if name_msg is None:
            return False
        name = name_msg.get("msg")

        RecvSend.sendJSON(conn, "state", "REGISTER_PASS")
        pass_msg = RecvSend.recv_msg(conn)
        if pass_msg is None:
            return False
        passwd = pass_msg.get("msg")

        result = self.queryDB("User", "create", {"name": name, "passwd": passwd})
        if result.get("status") == "ok":
            RecvSend.sendJSON(conn, "result", "REGISTER_OK")
            return True
        elif result.get("status") == "error" and result.get("msg") == "duplicated":
            RecvSend.sendJSON(conn, "error", "REGISTER_DUPLICATE")
            return False
        else:
            RecvSend.sendJSON(conn, "error", "REGISTER_FAIL")
            return False

    def login(self, conn):
        RecvSend.sendJSON(conn, "state", "LOGIN_NAME")
        name_msg = RecvSend.recv_msg(conn)
        if name_msg is None:
            return None
        name = name_msg.get("msg")

        result = self.queryDB("User", "query", {"conditions": {"name": name}})
        if not result.get("data"):
            RecvSend.sendJSON(conn, "error", "NOT_REGISTERED")
            return None

        RecvSend.sendJSON(conn, "state", "LOGIN_PASS")
        pass_msg = RecvSend.recv_msg(conn)
        if pass_msg is None:
            return None
        passwd = pass_msg.get("msg")

        user_info = result.get("data")[0]
        if passwd != user_info.get("passwd"):
            RecvSend.sendJSON(conn, "error", "WRONG_PASSWORD")
            return None
        if user_info.get("status") == "online":
            RecvSend.sendJSON(conn, "error", "ALREADY_ONLINE")
            return None

        tmp = self.queryDB("User", "update", {"name": name, "status": "online"})
        if tmp.get("status") == "error":
            RecvSend.sendJSON(conn, "error", "DB_ERR")
            return None

        RecvSend.sendJSON(conn, "auth", "LOGIN_SUCCESS", id=name)
        self.online_users[name] = conn
        return name

    def logout(self, conn, username=None, force=False):
        if username:
            try:
                print(f"[DEBUG] loggint out user {username}")
                if not force:
                    RecvSend.sendJSON(conn, "result", "LOGOUT_OK")
                del self.online_users[username]
                self.queryDB("User", "update", {"name": username, "status": "offline"})
                if force:
                    self.leaveServer(conn)
            except Exception:
                pass
    
    def leaveServer(self, conn):
        try:
            conn.shutdown(socket.SHUT_RDWR)
            conn.close()
        except Exception:
            pass

    def Login(self, conn):
        username = None
        try:
            RecvSend.sendJSON(conn, "command", "CLEAR_CLIENT")
            while True:
                if username is None:
                    # Tell client to show login menu
                    RecvSend.sendJSON(conn, "state", "SHOW_LOGIN_MENU")
                    msg = RecvSend.recv_msg(conn)
                    if msg is None:
                        break
                    action = self.message_action_or_response(msg)
                    if action == "1": # register
                        self.register(conn)
                        continue
                    elif action == "2": # login
                        username = self.login(conn)
                        if username is None:
                            continue
                    elif action == "3": # leave
                        RecvSend.sendJSON(conn, "result", "GOODBYE")
                        self.leaveServer(conn)
                        return
                    else:
                        RecvSend.sendJSON(conn, "error", "INVALID_ACTION")
                else:
                    logged_out = self.Lobby(conn, username)
                    if logged_out: # safe logout, back to login menu
                        username = None
                        continue
                    else: # forced leave game
                        return
        except (OSError, ConnectionResetError):
            self.logout(conn, None, force=True)
        except KeyboardInterrupt:
            raise

    def Lobby(self, conn, username):
        try:
            while True:
                RecvSend.sendJSON(conn, "state", "SHOW_LOBBY_MENU")
                msg = RecvSend.recv_msg(conn)
                if msg is None:
                    continue
                action = self.message_action_or_response(msg)
                if action == "1": # browse game
                    self.BrowseGameLib(conn, username)
                elif action == "2": # rate game
                    self.RateGame(conn, username)
                elif action == "3": # delete, processed at client side
                    continue
                elif action == "4": # start game
                    self.PlayGame(conn, username)
                    continue
                elif action == "5":
                    print(f"{username} logged out!")
                    self.logout(conn, username, force=False)
                    return True
                else:
                    RecvSend.sendJSON(conn, "error", "INVALID_ACTION")
        except (OSError, ConnectionResetError):
            self.logout(conn, username, force=True)
            return False
        except KeyboardInterrupt:
            raise
        except Exception as e:
            RecvSend.sendJSON(conn, "error", "LOBBY_ERR")
            return False
        
    def RateGame(self, conn, username):
        RecvSend.sendJSON(conn, "state", "RATE_GAME_FLOW_START")
        user_data = self.queryDB("User", "query", {"conditions": {"name": username}}).get("data")[0]
        played_game = user_data.get("played_game") or {}
        
        game_list = self.queryDB("Game", "query", {"conditions": {}}).get("data")
        game_name_list = [game.get("game_name") for game in game_list]

        # only return those player played, and game is still in DB
        available_games = {
            game: count
            for game, count in played_game.items()
            if game in game_name_list
        }
        print(f"[DEBUG] Returning available game list to rate : {available_games}")
        
        RecvSend.sendJSON(conn, "game_list", "", game_list=available_games)
        
        game_name = RecvSend.recv_msg(conn).get("msg")
        if game_name == "ABORT":
            print("[DEBUG] Cancelled rate game.")
            return
        
        RecvSend.sendJSON(conn, "state", "WRITING_COMMENT")
        data = RecvSend.recv_msg(conn)
        comment = data.get("comment")
        score = data.get("score")
        
        res = self.queryDB("GameComments", "create", {"game_name": game_name, "username": username, "comment": comment, "score": score}).get("'status")
        if res == "error":
            RecvSend.sendJSON(conn, "error", "Error while writing comments...")

    def BrowseGameLib(self, conn, username):
        # send list -> client side display -> choose game -> full details (rate + comments) -> loop until user leave the list
        while True:
            RecvSend.sendJSON(conn, "state", "BROWSE_GAME_FLOW_START")
            game_list = self.queryDB("Game", "query", {"conditions": {}}).get("data")
            
            game_name_list = []
            
            for game in game_list:
                game_name_list.append(game.get("game_name"))
            
            print(f"[DEBUG] Sent the available games to client. {game_name_list}")
            RecvSend.sendJSON(conn, "game_list", "", game_list=game_name_list)
            
            msg = RecvSend.recv_msg(conn)
            # print(f"[DEBUG] Received msg {msg} @ BrowseGameLib from user.")
            
            if msg is None or msg.get("msg") == "BROWSE_ABORT":
                print(f"[DEBUG] Browse abort.")
                return
            
            game_name = msg.get("game_name")
            self.SendGameDetails(conn, username, game_name)
            
    def SendGameDetails(self, conn, username, game_name):
        print(f"Trying to send game info of {game_name} to user.")
        RecvSend.sendJSON(conn, "state", "SHOW_GAME_DETAILS")
        game_data = self.queryDB("Game", "query", {"conditions": {"game_name": game_name}}).get("data")[0]
        config_path = os.path.join(game_data.get("path"), "config.json")
        with open(config_path, "r") as f:
            config = json.load(f)
        game_type = config.get("game_type")
        max_players = config.get("max_players")
        des = config.get("description")
        comments = self.queryDB("GameComments", "query", {"conditions": {"game_name": game_name}}).get("data")
        del game_data["path"]
        del game_data["name"]
        details = {
            **game_data,
            "game_type": game_type,
            "max_players": max_players,
            "description": des,
        }
        RecvSend.sendJSON(conn, "game_details", "", game_details=details)
        RecvSend.sendJSON(conn, "comments", "", comments=comments)
        print(f"info sent! {details}")
        res = RecvSend.recv_msg(conn)
        if res.get("type") == "DOWNLOAD":
            self.DownloadGame(conn, username, res.get("game_name"))
        elif res.get("type") == "RETURN":
            print("[DEBUG] Returning to browse game.")
        return

    def DownloadGame(self, conn, username, game_name):
        RecvSend.sendJSON(conn, "state", "DOWNLOAD_GAME")
        data = self.queryDB("Game", "query", {"conditions": {"game_name": game_name}}).get("data")
        if data:
            game_data = data[0]
        else:
            RecvSend.sendJSON(conn, "error", "ABORT", reason="Couldn't fetch game from database.")
            return False
        
        return self.sendGameFiles(conn, username, game_data)
    
    def sendGameFiles(self, conn, username, game_data):
        print(f"[INFO] Sending game files to user...")
        game_path = game_data.get("path")
        config_path = os.path.join(game_path, "config.json")
        game_client_path = os.path.join(game_path, "game_client.py")

        files_to_send = [
            ("config.json", config_path),
            ("game_client.py", game_client_path),
        ]
        
        for filename, local_path in files_to_send:
            success = self.send_file(conn, local_path, filename)
            if not success:
                print(f"[ABORT] Stopping upload due to error with {filename}")
                RecvSend.sendJSON(conn, "error", "ABORT")
                return False

        print("[DEBUG] Fully sent required files.")
        RecvSend.sendJSON(conn, "action", "COMPLETE")
        return True

    def send_file(self, conn, file_path, target_filename):
        if not os.path.exists(file_path):
            print(f"[ERROR] File not found: {file_path}")
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
            RecvSend.send_msg(conn, upload)
            
            print(f"[FILE SENT] Sent {target_filename} ({len(file_bytes)} bytes)")
            return True
        except (OSError, ConnectionResetError):
            raise
        except Exception as e:
            print(f"[ERROR] Failed to send {target_filename}: {e}")
            return False
        
    def PlayGame(self, conn, username):
        try:
            RecvSend.sendJSON(conn, "state", "SHOW_AVAILABLE_GAMES")
            game_list = self.queryDB("Game", "query", {"conditions": {}}).get("data")

            RecvSend.sendJSON(conn, "game_list", "", game_list=game_list)

            msg = RecvSend.recv_msg(conn)
            selected_game = msg.get("msg")
            if selected_game is None:
                RecvSend.sendJSON(conn, "error", "Invalid game selection.")
                return
            elif msg.get("type") == "ABORT":
                print("[DEBUG] abort, no game on server")
                return

            RecvSend.sendJSON(conn, "state", "VERIFY_GAME_VERSION")
            # Get the latest version from DB
            game_data = self.queryDB("Game", "query", {"conditions": {"game_name": selected_game}}).get("data")[0]
            if game_data is None:
                RecvSend.sendJSON(conn, "GAME_DELETED", "")
                print(f"[DEBUG] Game {game_name} is not found @ PlayGame")
                return False
            
            latest_version = game_data.get("version")
            RecvSend.sendJSON(conn, "version", "", version=latest_version)
            game_name = game_data.get("game_name")

            msg = RecvSend.recv_msg(conn)
            status = msg.get("status")
            
            if status == "PASS":
                print("[INFO] User side verification passed!")
            elif status == "DOWNLOAD":
                res = self.DownloadGame(conn, username, game_name)
                if not res:
                    print("[ERROR] Couldn't send file to user.")
                    return
            elif status == "ABORT":
                print("[INFO] User aborted")
                return
            
            # client action (JOIN / CREATE / BACK)
            RecvSend.sendJSON(conn, "state", "JOIN_CREATE_ROOM")
            msg = RecvSend.recv_msg(conn)
            action = msg.get("action")

            if action == "JOIN_ROOM":
                self.JoinRoom(conn, username, selected_game)
            elif action == "CREATE_ROOM":
                self.CreateRoom(conn, username, selected_game, game_data)
            elif action == "BACK":
                RecvSend.sendJSON(conn, "info", "Returning to menu.")
                return
            else:
                RecvSend.sendJSON(conn, "error", "Invalid room action.")
        except (ConnectionError, ConnectionResetError):
            raise
        except Exception as e:
            print(f"[ERROR] {e} @ PlayGame server")
            RecvSend.sendJSON(conn, "error", "Server error during PlayGame.")
    
    def get_room_lock(self, hostName):
        with self.global_lock:
            if hostName not in self.room_locks:
                self.room_locks[hostName] = threading.Lock()
            return self.room_locks[hostName]
    
    def JoinRoom(self, conn, username, game_name):
        RecvSend.sendJSON(conn, "state", "SHOW_ROOM_LIST")
        room_list = self.queryDB("Room", "query", {"conditions": {"game_name": game_name, "status": "waiting"}}).get("data")
        # print("[DEBUG] Room query @ join room1")
        RecvSend.sendJSON(conn, "room_list", "", room_list=room_list)
        
        hostName = RecvSend.recv_msg(conn).get("msg")
        if hostName == "ABORT":
            print("[DEBUG] Join room flow aborted")
            return
        
        # search again to make sure other didn't join and lock to prevent data rush while actually joining
        room_lock = self.get_room_lock(hostName)
        with room_lock:
            room_status = self.queryDB("Room", "query", {"conditions": {"hostName": hostName}}).get("data")
            # print("[DEBUG] Room query @ join room2")
            
            if len(room_status) == 0:
                RecvSend.sendJSON(conn, "error", "Room is closed by host...")
                return
            else:
                room_status = room_status[0]
                new_status = room_status.get("status")
                if new_status == "full":
                    RecvSend.sendJSON(conn, "error", "Room is full...")
                    return
            
            new_players = room_status.get("players")
            new_players.append(username)
            if len(new_players) == room_status.get("max_players"):
                new_status = "full"
            
            self.queryDB("Room", "update", {"hostName": hostName, "players": new_players, "status": new_status})
        
        # join after safe udpate
        self.room_client_receiver(conn, username, hostName, False, game_name)
        
    def CreateRoom(self, conn, username, game_name, game_data):
        max_players = game_data.get("max_players")
        res = self.queryDB("Room", "create", 
                     {"hostName": username,
                      "status": "waiting",
                      "players": [username],
                      "game_name": game_name,
                      "max_players": max_players
                      }).get("status")
        
        if res == "ok":
            RecvSend.sendJSON(conn, "result", "ROOM_CREATED")
            self.room_client_receiver(conn, username, username, True, game_name)
        else:
            RecvSend.sendJSON(conn, "error", "CAN'T_CREATE_ROOM")
        
    def room_client_receiver(self, conn, username, hostName, isOwner, game_name):
        identity = "HOST"
        if not isOwner:
            identity  = "GUEST"
            # notify player joined
            result = self.queryDB("Room", "query", {"conditions" : {"hostName": hostName}})
            print("[DEBUG] Room query @ room client receiver")
            roomInfo = result.get("data")[0]
            players = roomInfo.get("players")
            for player in players:
                if player != username:
                    RecvSend.sendJSON(self.online_users[player], "room_info", f"Player {username} joined!")
        
        try:
            while True:
                RecvSend.sendJSON(conn, "state", "IN_ROOM", identity=identity)
                msg = RecvSend.recv_msg(conn)

                state = msg.get("state")
                message = msg.get("msg")
                
                if state == "CHECK_VERSION":
                    print(f"[DEBUG] User {username} starting check version flow")
                    res = self.checkVersion(username, game_name)
                
                if state == "IN_ROOM":
                    check = self.inRoom(conn, username, hostName, isOwner, game_name, message)
                    if check is not None and check == "LEAVE":
                        return
                    
                if state == "GAME_START":
                    self.inGame(conn, username, game_name)
                    
                if state == "ROOM_CLOSED":
                    print(f"[DEBUG] Room closed, kicking user: {username}")
                    return

        except Exception as e:
            print(f"[DEBUG] Error {e} @ room_client_receiver, calling leave room function.")
            self.handle_leave_room(username, hostName, isOwner)
            raise
    
    def inRoom(self, conn, username, hostName, isOwner, game_name, msg):
        print(f"{username} @ inRoom, sent {msg}")

        if msg == "/start" and isOwner:
            result = self.queryDB("Room", "query", {"conditions" : {"hostName": hostName}})
            # print("[DEBUG] Room query @ inRoom")
            roomInfo = result.get("data")[0]
            players = roomInfo.get("players")
            if len(players) == roomInfo.get("max_players"):
                for player in players:
                    RecvSend.sendJSON(self.online_users[player], "state", "CHECK_BEFORE_GAME")
                res = self.checkVersion(username, game_name)
                if res == False:
                    print("[DEBUG] Game deleted, forcing close room.")
                    return self.handle_leave_room(username, hostName, isOwner)

                success = self.open_game_server(players, game_name)
                if success:
                    self.queryDB("Room", "update", {"hostName": username, "status": "playing"})
                    self.inGame(conn, username, game_name)
                    self.queryDB("Room", "update", {"hostName": username, "status": "full"})
                else: # can't open game server (game deleted while the room is open)
                    return self.handle_leave_room(username, hostName, isOwner)
            else:
                RecvSend.sendJSON(conn, "error", "Not enough players to start...")

        elif msg == "/leave":
            return self.handle_leave_room(username, hostName, isOwner)
        
        else: # modify to chatting if have time
            print(f"[DEBUG] Unknown command : {msg} from {username}")
    
    def handle_leave_room(self, username, hostName, isOwner):
        result = self.queryDB("Room", "query", {"conditions" : {"hostName": hostName}})
        print(f"[DEBUG] Handling {username} calling leave room.")
        roomInfo = result.get("data")
        if roomInfo:
            roomInfo = roomInfo[0]
        else:
            return "LEAVE"

        players = roomInfo.get("players")
        if isOwner:
            if len(players) > 1:
                for player in players:
                    if player != hostName:
                        RecvSend.sendJSON(self.online_users[player], "room_info", f"Host {username} closed the room...")
                        RecvSend.sendJSON(self.online_users[player], "state", "ROOM_TERMINATED")
            self.queryDB("Room", "delete", {"hostName": username})
            return "LEAVE"
        else:
            if len(players) > 1:
                delete_index = None
                for i, p in enumerate(players):
                    if p != username:
                        RecvSend.sendJSON(self.online_users[p], "room_info", f"Player {username} left the room.")
                    else:
                        delete_index = i
                if delete_index is not None:
                    del players[delete_index]
            self.queryDB("Room", "update", {"hostName": hostName, "players": players, "status": "waiting"})
            return "LEAVE"
    
    def inGame(self, conn, username, game_name):
        print("Trap state")
        while True:
            msg = RecvSend.recv_msg(conn).get("msg")
            if msg == "GAME_END":
                print(f"[DEBUG] Received game end signal from user: {username}.")

                user_data = self.queryDB("User", "query", {"conditions": {"name": username}}).get("data")[0]
                
                played = user_data.get("played_game", {})
                if played is None:
                    played = {}
                    
                current_count = played.get(game_name, 0)
                played[game_name] = current_count + 1
                
                self.queryDB("User", "update", {
                    "name": username,
                    "played_game": played
                })
                print("[DEBUG] update complete")
                return # return to room
    
    def open_game_server(self, user_list, game_name):
        print(f"[DEBUG] Trying to open game server...")
        game_data = self.queryDB("Game", "query", {"conditions": {"game_name": game_name}}).get("data")[0]
        
        ip = self.get_ip()
        port = self.get_free_port()
        game_path = game_data["path"]
        print(f"[DEBUG] Game path: {game_path}, IP: {ip}, PORT: {port}")
        
        try:
            start_game_server = self.load_start_game_server(game_path)
            t = threading.Thread(target=start_game_server, args=(ip, port, user_list), daemon=True)
            t.start()
        except FileNotFoundError:
            for user in user_list:
                conn_user = self.online_users[user]
                RecvSend.sendJSON(conn_user, "ERROR", "GAME_DELETED_FROM_SERVER")
            print(f"[DEBUG] Game Server not found!")
            return False
        
        for user in user_list:
            conn_user = self.online_users[user]
            RecvSend.sendJSON(conn_user, "state", "GAME_START", ip=ip, port=port)
        
        print(f"[DEBUG] Game Server oppened!")
        return True
    
    def load_start_game_server(self, game_path):
        module_path = os.path.join(game_path, "game_server.py")

        spec = importlib.util.spec_from_file_location("game_server_dynamic", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module.start_game_server
    
    def get_ip(self):
        print("[DEBUG] Getting game IP...")
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip
    
    def get_free_port(self, start=40000, end=50000):
        print("[DEBUG] Getting game PORT...")
        with self.port_lock:
            for port in range(start, end):
                if port in self.used_ports:
                    continue
                # test if port actually free at the OS level
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    if s.connect_ex(("0.0.0.0", port)) != 0:
                        self.used_ports.add(port)
                        return port
            raise RuntimeError("No free ports available")
    
    def checkVersion(self, username, game_name): # check before the game starts
        game_data = self.queryDB("Game", "query", {"conditions": {"game_name": game_name}}).get("data")
        print(f"[DEBUG] Checking whether user: {username}'s game file version is up to date...")
        conn = self.online_users[username]
        if not game_data:
            RecvSend.sendJSON(conn, "GAME_DELETED", "")
            print(f"[DEBUG] Game {game_name} is not found @ checkVersion")
            return False

        game_data = game_data[0]
        latest_version = game_data.get("version")
        RecvSend.sendJSON(conn, "version", "", version=latest_version)
        print(f"[DEBUG] Sent to user: {username} the latest verion {latest_version}")

        msg = RecvSend.recv_msg(conn)
        status = msg.get("status")
        
        if status == "PASS":
            print(f"[DEBUG] Received Version Check Pass from {username}")
            return True
        elif status == "DOWNLOAD":
            return self.sendGameFiles(conn, username, game_data)
        elif status == "ABORT":
            return False

    def cleanUp(self):
        try:
            self.queryDB("SERVER_SHUTDOWN", "SERVER_SHUTDOWN", "SERVER_SHUTDOWN")
        except Exception:
            pass

    def main(self):
        self.connDB()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.HOST, self.PORT))
        s.listen()
        try:
            while True:
                conn, addr = s.accept()
                t = threading.Thread(target=self.Login, args=(conn,), daemon=True)
                t.start()
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanUp()
            try:
                s.shutdown(socket.SHUT_RDWR)
                s.close()
            except Exception:
                pass
            sys.exit(0)

if __name__ == "__main__":
    server = LobbyServer()
    server.main()
