import struct
import json
import socket



def send_msg(sock, data: str):
    # 叫之前先自己用成json這邊不處理
    try:
        data = data.encode()
        length = len(data)
        if length == 0:
            raise ValueError(f"Invalid message length: {length}")

        # 接下來訊息的size
        header = struct.pack("!I", length)
        msg = header + data

        # send 到一半
        total_sent = 0
        while total_sent < len(msg):
            bytes_sent = sock.send(msg[total_sent:])
            if bytes_sent == 0:
                raise ConnectionError("[ERROR]: Couldn't send data, connection closed.")
            total_sent += bytes_sent
    except:
        raise

def recv_exact(sock, num_bytes: int) -> bytes:
    # 收指定大小的data
    try:
        buf = b""
        while len(buf) < num_bytes:
            chunk = sock.recv(num_bytes - len(buf))
            if not chunk:
                raise ConnectionError("[ERROR]: Couldn't recv data, connection closed.")
            buf += chunk
        return buf
    except:
        raise

def recv_msg(sock) -> bytes:
    # 先收固定大小的header, 4 bytes
    try:
        header = recv_exact(sock, 4)
        if len(header) < 4:
            raise ConnectionError("[ERROR]: Wrong header.")

        # 由header得到接下來的data大小 unpack returns tuple
        (length,) = struct.unpack("!I", header)

        if length == 0:
            raise ValueError(f"[ERROR]: Invalid message length: {length}")

        data = recv_exact(sock, length)
        data = data.decode()
        # print(f"[DEBUG] Received data @ RecvSend : {data}")
        return json.loads(data)
    except:
        raise

def sendJSON(conn, msg_type, msg, **kwargs):
    try:
        data = makeJSON(msg_type, msg, **kwargs)
        send_msg(conn, data)
    except:
        raise

def makeJSON(msg_type, msg, **kwargs):
    try:
        msg = {"type": msg_type, "msg": msg}
        msg.update(kwargs) # 把多定義的 (kwargs) field也加上去
        return json.dumps(msg)
    except:
        raise