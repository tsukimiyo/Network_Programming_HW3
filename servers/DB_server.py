import socket
import json
from datetime import datetime
import threading
import os
import RecvSend
import sys
import base64
import shutil

DB_FILE = "DB.json"
STORAGE_DIR = "server_storage"
HOST = "140.113.17.13" # 140.113.17.{11|12|13|14} (linux3 : 13)
PORT = 20850

db_lock = threading.Lock()

# Ensure storage directory exists
if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)

# Initialize DB
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        db = json.load(f)
else:
    # Added "Game" collection
    db = {"User": {}, "Developer": {}, "Room": {}, "Game": {}, "GameComments": {}} 

def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)

def handle_action(collection, action, data, conn=None):
    if action == "SERVER_SHUTDOWN":
        cleanup()
        return "SHUTDOWN"

    print(f"[DEBUG] Waiting for db_lock: {action}")
    with db_lock:
        print(f"[DEBUG] Acquired db_lock: {action}")
        if collection not in db:
            return {"status": "error", "msg": f"Unknown collection: {collection}"}

        cur_table = db[collection]
        
        if collection == "Game" and action == "UPLOAD_GAME":
            print("Uploading game.")
            return handle_game_upload(data)
        
        if collection == "User" or collection == "Developer":
            primary_key = "name"
        elif collection == "Room":
            primary_key = "hostName"
        elif collection == "Game" or collection == "GameComments":
            primary_key = "game_name"

        if action == "create":
            key = data.get(primary_key)
            if key in cur_table and collection != "GameComments":
                return {"status": "error", "msg": "duplicated"}
            
            if collection == "User":
                data["status"] = "offline"
                data["played_games"] = {}
                
            elif collection == "Developer":
                data["status"] = "offline"

            elif collection == "Room":
                now = datetime.now()
                data["createdAt"] = now.strftime("%Y/%m/%d %H:%M:%S")
            
            elif collection == "GameComments":
                game_name = data["game_name"]
                username = data["username"]
                comment = data["comment"]
                score = float(data.get("score", 0))

                if game_name not in cur_table:
                    cur_table[game_name] = {}

                cur_table[game_name][username] = {
                    "comment": comment,
                    "score": score
                }

                # update score of game
                comments = cur_table[game_name]
                total_score = sum(entry.get("score", 0) for entry in comments.values())
                num_scores = len(comments)
                avg_score = total_score / num_scores if num_scores > 0 else 0.0

                # --- Update the Game collection with new average ---
                if "Game" in db and game_name in db["Game"]:
                    db["Game"][game_name]["rate"] = f"{avg_score:.1f}/5.0"
                    print(f"[DEBUG] Updated game rating: {game_name} = {avg_score:.1f}/5.0")
                else:
                    print(f"[WARN] Game '{game_name}' not found in Game collection.")

                save_db()
                return {"status": "ok", "data": "comment_added"}

            if collection != "GameComments":
                cur_table[key] = data
                save_db() # Save while locked
                return {"status": "ok", "data": key}
        
        elif action == "read":
            key = data.get(primary_key)
            if key not in cur_table:
                return {"status": "error", "msg": f"Requested key: {key} not found."}
            return {"status": "ok", "data": cur_table[key]}
        
        elif collection == "GameComments" and action == "query":
            game_name = data["conditions"].get("game_name")
            comments = cur_table.get(game_name, {})

            return {
                "status": "ok",
                "data": [
                    {
                        "username": u,
                        "comment": info.get("comment", ""),
                        "score": info.get("score", 0)
                    }
                    for u, info in comments.items()
                ]
            }
        
        elif action == "query":
            conditions = data.get("conditions")
            if conditions is None:
                return {"status": "error", "msg": "missing query parameters"}
            results = []
            for name, record in cur_table.items():
                if all(str(record.get(k)) == str(v) for k, v in conditions.items()):
                    results.append({"name": name, **record})
            return {"status": "ok", "data": results}

        elif action == "update":
            key = data.get(primary_key)
            if key not in cur_table:
                return {"status": "error", "msg": f"Requested key: {key} not found."}
            cur_table[key].update(data)
            save_db()
            return {"status": "ok", "data": cur_table[key]}
        
        elif action == "delete":
            key = data.get(primary_key)
            if key not in cur_table:
                return {"status": "error", "msg": f"Requested key: {key} not found."}
            
            # If deleting a game, remove files too
            if collection == "Game":
                game_path = os.path.join(STORAGE_DIR, key)
                if os.path.exists(game_path):
                    shutil.rmtree(game_path) # Recursively delete folder

            del cur_table[key]
            save_db()
            return {"status": "ok"}

        else:
            return {"status": "error", "msg": f"Invalid action: {action}"}

def handle_game_upload(data):
    try:
        username = data["username"]
        game_name = data["game_name"]
        max_players = data["max_players"]
        version = data["version"]
        game_files = data["files"]

        game_dir = os.path.join(STORAGE_DIR, game_name)

        # del previous version
        if os.path.exists(game_dir):
            shutil.rmtree(game_dir)
        os.makedirs(game_dir)

        for filename, b64_content in game_files.items():
            try:
                file_bytes = base64.b64decode(b64_content)
            except Exception as e:
                raise Exception(f"Base64 decode failed for {filename}: {e}")

            save_path = os.path.join(game_dir, filename)
            with open(save_path, "wb") as f:
                f.write(file_bytes)

        db["Game"][game_name] = {
            "game_name": game_name,
            "owner": username,
            "version": version,
            "path": game_dir, # for server only
            "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "max_players": max_players,
            "downloads": 0,
            "rate": "N/A" # would be {avg_score} / 5.0 
        }
        save_db()

        print(f"[DB] Uploaded: {game_name} v{version} by {username}")
        return {"status": "ok", "game": f"{game_name} uploaded"}

    except Exception as e:
        print(f"[ERROR] {e} @ handling game upload.")

        # Cleanup partially created directory
        try:
            game_dir = os.path.join(STORAGE_DIR, game_name, version)
            if os.path.exists(game_dir):
                shutil.rmtree(game_dir)
        except:
            pass

        return {"status": "error", "game": f"failed to upload {game_name}", "reason": str(e)}


def handle_conn(conn, addr, isLobby):
    print(f"Client {addr} connected.")
    try:
        while True:
            request = RecvSend.recv_msg(conn)
            if not request:
                return
            
            # print(f"[DEBUG] Received Request : {request}")
            collection = request.get("collection")
            action = request.get("action")
            data = request.get("data")
            
            if collection == "SHUTDOWN":
                break
            
            if collection not in db:
                result = {"status": "error", "msg": f"Unknown collection: {collection}"}
            else:
                result = handle_action(collection, action, data)
                save_db()
            
            # print(f"[DEBUG] Returning data {result}")
            resJSON = json.dumps(result)
            RecvSend.send_msg(conn, resJSON)
            print(f"[DEBUG] Data sent.")
    except Exception as e:
        print(f"[ERROR] Unexpected error with client {addr}: {e}")
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()
        print(f"Client {addr} disconnected.")
        cleanup(isLobby)

def auth(conn, addr):
    ans = RecvSend.recv_msg(conn).get("identity")
    if ans is None:
        print("[ERROR] Unknown identity tried to connect to DB.")
        return
    elif ans == "LOBBY":
        isLobby = True
    elif ans == "DEV":
        isLobby = False
        
    handle_conn(conn, addr, isLobby)

def start_server(host=HOST, port=PORT): 
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
    s.bind((host, port))
    s.listen()
    print(f"DB Server running at {host}:{port}")
    fullCleanUp()
    try:
        while True:
            conn, addr = s.accept()
            threading.Thread(target=auth, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\nShutting down DB server.")
    finally:
        s.close()
        fullCleanUp()
        sys.exit(0)

def cleanup(isLobby):
    print(f"[DEBUG] Waiting for db_lock: cleanup")
    with db_lock:
        print(f"[DEBUG] Acquired db_lock: cleanup")
        if isLobby:
            for username in db["User"]:
                db["User"][username]["status"] = "offline"
            db["Room"].clear()
        else:
            for username in db["Developer"]:
                db["Developer"][username]["status"] = "offline"

        save_db()

def fullCleanUp():
    print(f"[DEBUG] Waiting for db_lock: fullCleanUp")
    with db_lock:
        print(f"[DEBUG] Acquired db_lock: fullCleanUp")
        for username in db["User"]:
            db["User"][username]["status"] = "offline"
        db["Room"].clear()
        for username in db["Developer"]:
            db["Developer"][username]["status"] = "offline"
        save_db()
    

if __name__ == "__main__":
    start_server()