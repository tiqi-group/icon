import select
import socket


def is_socket_closed(sock: socket.socket) -> bool:
    try:
        readable, _, _ = select.select([sock], [], [], 0)
        if readable:
            data = sock.recv(1, socket.MSG_PEEK)
            if not data:
                return True
    except OSError:
        return True
    return False
