from dataclasses import dataclass, field, asdict, is_dataclass
from socket import socket as Socket, AF_INET, SOCK_STREAM
import threading
import json
import uuid
from time import localtime, strftime
# import sys, signal

# def signal_handler(signal, frame):
#     print("\nprogram exiting gracefully")
#     sys.exit(0)

# signal.signal(signal.SIGINT, signal_handler)

CRLF = "\r\n"
DELIMITER = " "


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)


@dataclass
class Message:
    id: str
    sender: str  # user_id of the sender
    date: str  # str that reprent date
    subject: str  # Subject of the message
    content: str  # Content of the message


@dataclass
class Group:
    users: list[str] = field(default_factory=list)  # List of userid
    messages: list[Message] = field(default_factory=list)   # List of message
    connections: list[Socket] = field(default_factory=list)   # List of active socket connections to this group


# Utility functions for making JSON response messgae
def createResponse(status_code: int, type: str, data={}, error=""):
    # Add a space between `code` and `message`
    response = {
        "status": status_code,
        "type": type,
        "data": data,
        "error": error
    }
    response_json = json.dumps(response, cls=EnhancedJSONEncoder)
    return response_json.encode()


class BAGRequestHandler:

    def __init__(self, socket: Socket, groups: dict[str, Group], connection_pool: list[Socket]):
        self.socket = socket
        self.user_id = None
        self.groups = groups
        self.connection_pool = connection_pool
        self._stop_event = threading.Event()
        return

    def __call__(self):
        while not self._stop_event.is_set():
            try:
                self.wait_and_process_request()
            except ConnectionResetError:
                print(f"Client {self.user_id} exited")
                self.process_disconnect()
                return
            except Exception as error:
                print("Error processing request:", error)
                self.process_disconnect()
                return

    def process_get_groups(self):
        self.socket.sendall(createResponse(200, "GET_GROUPS", data={"groups": list(self.groups.keys())}))

    def process_get_users(self, group_id: str):
        users = [] if group_id not in self.groups else self.groups[group_id].users
        self.socket.sendall(createResponse(200, "GET_USERS", data={"users": users, "groupId": group_id}))

    def process_join_group(self, user_id, group_id):
        if group_id not in self.groups:
            return self.socket.sendall(createResponse(404, "JOIN_GROUP", error="Group name not exist"))
        group = self.groups[group_id]

        # Check if this connection is already in the group, because users can rejoin group
        # If already in, do nothing
        if self.socket in group.connections:
            return

        # Send message to everyone that a new user has joined group
        for connection in group.connections:
            connection.sendall(createResponse(200, "GROUP_NEW_USER", data={"userId": user_id, "groupId": group_id}))

        # Add new user into group
        group.users.append(user_id)
        group.connections.append(self.socket)
        # Notify user that group join is successful, and give users the last 2 messages of group
        last_two_messages = group.messages if len(group.messages) < 2 else group.messages[-2:]
        self.socket.sendall(
            createResponse(
                200, "JOIN_GROUP",
                {"groupId": group_id, "userId": user_id, "messages": last_two_messages}))
        return

    def process_post_message(self, group_id: str, subject: str, body: str):
        if group_id not in self.groups:
            return self.socket.sendall(createResponse(404, "POST_MESSAGE", error="Group name not exist"))

        group = self.groups[group_id]
        # If user is not in group yet, then disallows
        if self.user_id not in group.users:
            return self.socket.sendall(createResponse(304, "POST_MESSAGE", error="Forbidden"))
        message = Message(id=str(uuid.uuid4()), sender=self.user_id,
                          date=strftime("%H:%M:%S", localtime()), subject=subject, content=body)
        group.messages.append(message)
        # Tell everyone in group about the new message, which would also tell the current user
        for connection in group.connections:
            connection.sendall(createResponse(201, "NEW_MESSAGE", data={'groupId': group_id, "message": {
                "id": message.id,
                "sender": message.sender,
                "date": message.date,
                "subject": message.subject
            }}))

    def process_get_message(self, group_id, message_id):
        if group_id not in self.groups:
            return self.socket.sendall(createResponse(404, "GET_MESSAGE", error="Group name not exist"))
        group = self.groups[group_id]
        # If user is not in group yet, then disallows
        if self.user_id not in group.users:
            return self.socket.sendall(createResponse(304, "POST_MESSAGE", error="Forbidden"))
        # Credit: https://stackoverflow.com/a/10302859
        message = next((m for m in group.messages if m.id == message_id), None)
        if not message:
            return self.socket.sendall(createResponse(404, "GET_MESSAGE", error="Message id not found"))

        return self.socket.sendall(createResponse(200, "GET_MESSAGE", data={
            "message": {"id": message_id, "content": message.content},
            "groupId": group_id
        }))

    def process_disconnect(self):
        if self.socket in self.connection_pool:
            self.connection_pool.remove(self.socket)
        # Go through every group to find this socket and remove it
        for group_name, group in self.groups.items():
            if self.socket in group.connections:
                group.connections.remove(self.socket)
        self._stop_event.set()
        self.socket.close()

    def wait_and_process_request(self):
        request_message = self.socket.recv(4096).decode()
        if (not request_message):
            return
        # # Split the message by the endline character to get an array of lines
        # request_message_lines = request_message.splitlines()
        # # The request line is the 1st line in the message
        # # The remaining lines are the headers
        # request_info_line = request_message_lines[0]

        # # The request info line is assumed to be in format "GET <path> HTTP/1.1"
        # method, path, http_ver = request_info_line.split(" ")

 
        command, *info = request_message.splitlines()[0].split(DELIMITER)
        # Strip the carriage returns and excess spaces
        command = command.strip()
        info = [arg.strip() for arg in info]
        print(f"{command=}, {info=}")

        if command == "connect":
            # Expect info to have 1 argument
            if len(info) != 1:
                self.socket.sendall(createResponse(400, "CONNECT_LOGIN", error="Wrong request form"))
                return

            self.user_id, = info
            return self.socket.sendall(
                createResponse(200, "CONNECT_LOGIN", data={"userId": self.user_id}))

        if command == "join":
            if not self.user_id:
                self.socket.sendall(createResponse(400, "JOIN_GROUP", error="Not connected"))
                return

            group_id = ""
            if (len(info) == 0 or info[0] == ""):
                group_id = "PUBLIC"  # Default to "PUBLIC"
            else:
                group_id = info[0]
            self.process_join_group(self.user_id, group_id)

        elif command == "groups":
            if not self.user_id:
                self.socket.sendall(createResponse(400, "JOIN_GROUP", error="Not connected"))
                return
            self.process_get_groups()

        elif command == "users":
            if not self.user_id:
                self.socket.sendall(createResponse(400, "GET_USERS", error="Not connected"))
                return
            if (len(info) == 0 or info[0] == ""):
                group_id = "PUBLIC"  # Default to "PUBLIC"
            else:
                group_id = info[0]
            self.process_get_users(group_id)

        elif command == "post":
            if not self.user_id:
                return self.socket.sendall(createResponse(400, "POST_MESSAGE", error="Not connected"))
            
            # Expect info to have at least 1 item, `subject`
            if len(info) < 1:
                return self.socket.sendall(createResponse(400, "POST_MESSAGE", error="Wrong request form"))
            subject, *body_parts = info
            # Need to rejoin because the split() might have accidentally split the body
            body = DELIMITER.join(body_parts)
            # "post" commmands means post PUBLIC message
            self.process_post_message("PUBLIC", subject, body)

        elif command == "gpost":
            if not self.user_id:
                return self.socket.sendall(createResponse(400, "POST_MESSAGE", error="Not connected"))
            
            # Expect info to at least 2 items, `group_id`, and `subject``
            if len(info) < 2:
                return self.socket.sendall(createResponse(400, "POST_MESSAGE", error="Wrong request form"))
            group_id, subject, *body_parts = info
            body = DELIMITER.join(body_parts)
            self.process_post_message(group_id, subject, body)

        elif command == "message":
            if not self.user_id:
                return self.socket.sendall(createResponse(400, "GET_MESSAGE", error="Not connected"))
            # Expect info to have 1 items, `message_id`
            if len(info) != 1:
                return self.socket.sendall(createResponse(400, "GET_MESSAGE", error="Wrong request form"))
            message_id, = info
            self.process_get_message("PUBLIC", message_id)

        elif command == "gmessage":
            if not self.user_id:
                return self.socket.sendall(createResponse(400, "GET_MESSAGE", error="Not connected"))
            # Expect info to have 2 items, `group_id` and `message_id`
            if len(info) != 2:
                return self.socket.sendall(createResponse(400, "GET_MESSAGE", error="Wrong request form"))
            group_id, message_id = info
            self.process_get_message(group_id, message_id)

        elif command == "leave":
            if not self.user_id:
                return self.socket.sendall(createResponse(400, "LEAVE_GROUP", error="Not connected"))
            if (len(info) == 0 or info[0] == ""):
                group_id = "PUBLIC"  # Default to "PUBLIC"
            else:
                group_id = info[0]

            if group_id not in self.groups:
                return self.socket.sendall(createResponse(404, "LEAVE_GROUP", error="Group name not exist"))

            group = self.groups[group_id]
            if self.socket not in group.connections:
                # If user not in this group, they shouldn't leave
                return self.socket.sendall(createResponse(400, "LEAVE_GROUP", error="Not in group to leave"))
            # Else, remove the socket frm that group:
            group.connections.remove(self.socket)
            self.socket.sendall(createResponse(200, "LEAVE_GROUP", data={"userId": self.user_id, "groupId": group_id}))

            # Tell everyone that this person left
            for connection in group.connections:
                connection.sendall(createResponse(200, "USER_LEFT", data={"userId": self.user_id, "groupId": group_id}))

        elif command == "exit":
            self.process_disconnect()

        else:
            self.socket.sendall(createResponse(400, "GENERAL", error="Unsupported command"))
            return


class BAGServer:

    def __init__(self):
        SERVER_PORT = 6789
        self.server_socket = Socket(AF_INET, SOCK_STREAM)
        self.server_socket.bind(("", SERVER_PORT))
        self.connection_pool: list[Socket] = []
        self.groups = {
            "PUBLIC": Group(),
            "APPLE": Group(),
            "BANANA": Group(),
            "MANGO": Group(),
            "GRAPE": Group(),
            "ORANGE": Group(),
        }

    def main(self):
        print("Server started")
        self.server_socket.listen()
        while True:
            connection_socket, address = self.server_socket.accept()
            self.connection_pool.append(connection_socket)
            request_handler = BAGRequestHandler(connection_socket, self.groups, self.connection_pool)
            thread = threading.Thread(target=request_handler)
            thread.start()


def main():
    server = BAGServer()
    server.main()


if __name__ == "__main__":
    main()
