# Uncomment this to pass the first stage
import socket
import threading

DATABASE = {}


def expire_key(key: str) -> None:
    DATABASE.pop(key, None)


def extract_command(data: bytes) -> list[str]:
    decoded_data: str = data.decode()
    command = [arg for arg in decoded_data.split("\r\n")[:-1] if arg[0] not in "*$"]
    return command


def handle_connection(conn: socket.socket) -> None:
    PONG = b"+PONG\r\n"
    OK = b"+OK\r\n"
    NULL = b"$-1\r\n"

    # Receive data from the client
    while data := conn.recv(1024):
        print(f"Received {data}")

        if not data:
            continue

        # Parse the data and extract command
        command = extract_command(data)

        # Respond based on command recieved
        match command:
            case ["ping"]:
                response = PONG
            case ["echo", data]:
                response = f"+{data}\r\n".encode()
            case ["set", key, value]:
                DATABASE[key] = value
                response = OK
                print(f"Set key {key} to value {value}")
            case ["set", key, value, _, time]:
                DATABASE[key] = value
                threading.Timer(int(time) / 1000, expire_key, args=(key,)).start()
                response = OK
                print(f"Set key {key} to value {value} with expire time {time}")
            case ["get", key]:
                value = DATABASE.get(key, None)
                response = f"+{value}\r\n".encode() if value else NULL
            case _:
                print("Unknown Command:", command)
                response = f"-ERR unknown command '{command[0]}'\r\n".encode()

        conn.sendall(response)


def main() -> None:
    # Create a TCP server socket that listens on the localhost address and port 6379
    server_socket = socket.create_server(("localhost", 6379), reuse_port=True)

    # Start listening for incoming connections
    while True:
        # Accept a connection from a client
        conn, addr = server_socket.accept()
        print(f"Connected by {addr}")

        # Handle the connection in a new thread
        thread = threading.Thread(target=handle_connection, args=(conn,))
        thread.start()


if __name__ == "__main__":
    main()
