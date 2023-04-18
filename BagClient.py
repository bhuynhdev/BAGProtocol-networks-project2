import sys
import threading
import socket
from socket import socket as Socket
from time import sleep

CRLF = "\r\n"
BAG_SERVER_PORT = 6789
BAG_SERVER_HOST = "localhost"


class BAGClient:
    def __init__(self, onResponse) -> None:
        self.DEBUG = True
        self.current_response = ""
        self.responseCallback = onResponse
        self.socket: Socket = None
        self._stop_event = threading.Event()
        self.connect()

    def responseListener(self):
        while not self._stop_event.is_set():
            try:
                response = self.socket.recv(4096).decode()
                if response:
                    self.responseCallback(response)
            except ConnectionAbortedError as abortedError:
                with PRINT_LOCK:
                    print("CONNECTION STOPPED")
                self.disconnect()
                return
            except Exception as e:
                self.disconnect()
                return

    def connect(self):
        """
        Connect to the FTP server
        :param username: the username you use to login to your FTP session
        :param password: the password associated with the username
        """
        # TODO
        try:
            # Establish the client socket to connect to BAG server
            self.socket = Socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((BAG_SERVER_HOST, BAG_SERVER_PORT))
            responseListenerThread = threading.Thread(target=self.responseListener)
            responseListenerThread.start()

        except socket.herror as host_error:
            print("Host error when connecting", host_error)
            self.disconnect()
        except OSError as os_error:
            print("OS and IO error when connecting", os_error)
            self.disconnect()

    def send_command(self, command: str):
        self.socket.sendall(f"{command}{CRLF}".encode())

    def disconnect(self):
        self._stop_event.set()
        self.socket.close()


PRINT_LOCK = threading.Lock()

def printResponse(value):
    with PRINT_LOCK:
        print(value);

def main():

    bagClient = BAGClient(onResponse=printResponse)
    while not bagClient._stop_event.is_set():
        with PRINT_LOCK:
            print("Enter command: ", end="")
            command = input()
        if command.startswith("exit"):
            bagClient.disconnect()
            return
        bagClient.send_command(command)
        # Sleep a bit to wait for the ResponseListener thread to get a chance to print
        sleep(0.4)


if __name__ == "__main__":
    main()
