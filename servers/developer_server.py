import socket
import RecvSend
import threading
import json
import sys

class DeveloperServer():
    def __init__(self):
        self.HOST = "140.113.17.13" # 140.113.17.{11|12|13|14} (linux3 : 13)
        self.PORT = 20202
        self.DBIP = "140.113.17.13"
        self.DBPORT = 20850
        self.DB_socket = None
        self.online_users = {}
        self.db_sock_lock = threading.Lock()

    def connDB(self):
        self.DB_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.DB_socket.connect((self.DBIP, self.DBPORT))
        RecvSend.sendJSON(self.DB_socket, "AUTH", "", identity="DEV")

    def queryDB(self, collection: str, action: str, data):
        with self.db_sock_lock:
            payload = {
                "collection": collection,
                "action": action,
                "data": data
            }
            RecvSend.send_msg(self.DB_socket, json.dumps(payload))
            return RecvSend.recv_msg(self.DB_socket)

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

        result = self.queryDB("Developer", "create", {"name": name, "passwd": passwd})
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

        result = self.queryDB("Developer", "query", {"conditions": {"name": name}})
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

        tmp = self.queryDB("Developer", "update", {"name": name, "status": "online"})
        if tmp.get("status") == "error":
            RecvSend.sendJSON(conn, "error", "DB_ERR")
            return None

        RecvSend.sendJSON(conn, "auth", "LOGIN_SUCCESS", id=name)
        self.online_users[name] = conn
        return name

    def logout(self, conn, username=None, force=False):
        if username:
            try:
                if not force:
                    RecvSend.sendJSON(conn, "result", "LOGOUT_OK")
                del self.online_users[username]
                self.queryDB("Developer", "update", {"name": username, "status": "offline"})
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

    def DeveloperLogin(self, conn):
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
                    if action == "1":  # register
                        self.register(conn)
                        continue
                    elif action == "2":  # login
                        username = self.login(conn)
                        if username is None:
                            continue
                    elif action == "3":  # leave
                        RecvSend.sendJSON(conn, "result", "GOODBYE")
                        self.leaveServer(conn)
                        return
                    else:
                        RecvSend.sendJSON(conn, "error", "INVALID_ACTION")
                else:
                    logged_out = self.DeveloperLobby(conn, username)
                    if logged_out: # safe logout, back to login menu
                        username = None
                        continue
                    else: # forced leave game
                        return
        except (OSError, ConnectionResetError):
            self.logout(conn, None, force=True)
        except KeyboardInterrupt:
            raise

    def DeveloperLobby(self, conn, username):
        try:
            while True:
                RecvSend.sendJSON(conn, "state", "SHOW_LOBBY_MENU")
                msg = RecvSend.recv_msg(conn)
                if msg is None:
                    continue
                action = self.message_action_or_response(msg)
                if action == "1": # upload
                    RecvSend.sendJSON(conn, "state", "UPLOAD_FLOW_START")
                    self.UploadGame(conn, username)
                elif action == "2": # update
                    RecvSend.sendJSON(conn, "state", "UPDATE_FLOW_START")
                    self.UpdateGame(conn, username)
                elif action == "3": # delete
                    self.DeleteGame(conn, username)
                elif action == "4":
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

    def GetGameFiles(self, conn, username):
        try:
            files = {}
            while True:
                data = RecvSend.recv_msg(conn)
                print(data)
                if data.get("msg") == "GAME":
                    game_name = data.get("game_name")
                    version = data.get("version")
                    max_players = data.get("max_players")
                    print(f"[LOBBY] Received game basic info: {game_name}, {version}")
                    continue

                if data.get("msg") == "COMPLETE":
                    print("[LOBBY] Received upload complete signal")
                    break

                if data.get("msg") == "ABORT":
                    print("[LOBBY] Upload aborted by client.")
                    return None

                if "fileName" in data and "content" in data:
                    filename = data["fileName"]
                    content = data["content"]
                    files[filename] = content
                    print(f"[LOBBY] Received file: {filename}")
                    continue
            
            res = {
                "username": username,
                "game_name": game_name,
                "max_players": max_players,
                "version": version,
                "files": files
            }
            
            return res
        except:
            raise
        
    def UpdateGame(self, conn, username):
        try:
            game_list = self.queryDB("Game", "query", {"conditions": {"owner": username}}).get("data")
            print(f"[DEBUG] Server side sending game list {game_list}")
            RecvSend.sendJSON(conn, "game_list", game_list)

            res = self.GetGameFiles(conn, username)
            if res is None:
                return

            print(f"[DEBUG] Lobby passing data to DB")
            result = self.queryDB("Game", "UPLOAD_GAME", res)
            
            if result.get("status") == "ok":
                RecvSend.sendJSON(conn, "result", "UPDATE_SUCCESS")
                print("Update Success!")
            else:
                RecvSend.sendJSON(conn, "result", "UPDATE_FAILED")
                print("Update Failed...")

        except (ConnectionError, OSError, ConnectionResetError):
            raise
        except Exception as e:
            print(f"[ERROR] {e} @ upload game developer server")
            return

    def UploadGame(self, conn, username):
        try:
            res = self.GetGameFiles(conn, username)
            if res is None:
                return
            
            game_name = res.get("game_name")
            
            check = self.queryDB("Game", "query", {"conditions": {"game_name": game_name}}).get("data")
            if check:
                RecvSend.sendJSON(conn, "error", "UPLOAD_DUPLICATE")
                return

            print(f"Lobby passing data to DB")
            result = self.queryDB("Game", "UPLOAD_GAME", res)

            if result.get("status") == "ok":
                RecvSend.sendJSON(conn, "result", "UPLOAD_SUCCESS")
                print("Upload Success!")
            else:
                RecvSend.sendJSON(conn, "result", "UPLOAD_FAILED")
                print("Upload Failed...")

        except (ConnectionError, OSError, ConnectionResetError):
            raise
        except Exception as e:
            print(f"[ERROR] {e} @ upload game developer server")
            return

    def DeleteGame(self, conn, username):
        RecvSend.sendJSON(conn, "state", "REQUEST_DELETE_GAME")
        game_list = self.queryDB("Game", "query", {"conditions": {"owner": username}}).get("data")
        print(f"[DEBUG] Server side sending game list {game_list}")
        RecvSend.sendJSON(conn, "game_list", game_list)
        msg = RecvSend.recv_msg(conn)

        if msg is None or msg.get("msg") == "ABORT":
            # RecvSend.sendJSON(conn, "error", "DELETE_CANCEL")
            return

        game_name = msg.get("game_name")
        result = self.queryDB("Game", "delete", {"game_name": game_name})
        if result.get("status") == "ok":
            RecvSend.sendJSON(conn, "result", "DELETE_OK")
        else:
            RecvSend.sendJSON(conn, "error", "DELETE_FAIL")

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
                t = threading.Thread(target=self.DeveloperLogin, args=(conn,), daemon=True)
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
    server = DeveloperServer()
    server.main()
