import tkinter as tk
import customtkinter
import BagClient
import json
from CTkMessagebox import CTkMessagebox

def show_error(error_message):
    # Show some error message
    CTkMessagebox(title="Error", message=error_message, icon="cancel")

def create_system_message(response_type, data, error=""):
    if error:
        return f"Error: {error}"
    if response_type == "JOIN_GROUP":
        group_id, messages = data['groupId'], data['messages']
        response = f"Joined group {group_id}."
        if not messages:
            response += "\nNo recent messages to view"
        else:
            response += f"\nMost recent messages: {json.dumps(messages)}"
        return response
    if response_type == "GROUP_NEW_USER":
        group_id, user_id = data['groupId'], data['userId']
        return f"Group {group_id} has new user: {user_id}"
    if response_type == "GET_GROUPS":
        return f"Groups: {', '.join(data['groups'])}"
    if response_type == "GET_USERS":
        users = data['users']
        group_id = data['groupId']
        return f"Users in {group_id}: {users}"
    if response_type == "GROUP_NEW_USER":
        group_id, user_id = data['groupId'], data['userId']
        return f"Group {group_id} have new user: {user_id}"
    if response_type == "GET_MESSAGE":
        id, content = data['message']['id'], data['message']['content']
        return f"Message {id}: {content}"
    if response_type == 'NEW_MESSAGE':
        message, group_id = data['message'], data['groupId']
        return f"New message in group {group_id}: '{message['id']}: {message['subject']} by {message['sender']} at {message['date']}'"
    if response_type == "CONNECT_LOGIN":
        user_id = data['userId']
        return f'Welcome {user_id} to BAG. Join a group with `join`, or get list of groups with `groups`'
    if response_type == 'LEAVE_GROUP':
        group_id= data['groupId']
        return f"Left group {group_id}"
    if response_type == 'USER_LEFT':
        group_id, user_id = data['groupId'], data['userId']
        return f"User {user_id} have left group {group_id}"


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.bagClient = BagClient.BAGClient(onResponse=self.handleBAGResponse)

        self.geometry("650x500")
        self.title("BAG Interface")
        self.minsize(300, 200)

        # create 3x2 grid system
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        self.main_ui = customtkinter.CTkTextbox(master=self, state="disabled")
        self.main_ui.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 0), sticky="nsew")

        self.command_bar = customtkinter.CTkEntry(master=self, height=25, placeholder_text="Type command here", font=("Fira Code", 13))
        self.command_bar.grid(row=1, column=0, padx=20, pady=(20, 0), sticky="ew")
        self.command_bar.bind('<Return>', lambda event: self.submit_command())

        self.button = customtkinter.CTkButton(master=self, command=self.submit_command, text="Submit")
        self.button.grid(row=1, column=1, padx=20, pady=(20, 0), sticky="ew")

        self.system_message = customtkinter.CTkTextbox(self, state="disabled", height=70, font=("Fira Code", 13))
        self.system_message.grid(row=2, column=0, columnspan=2, padx=20, pady=20, sticky="ew")

    def handleBAGResponse(self, response):
        response = json.loads(response)
        if response['status'] >= 300:
            show_error(create_system_message(response['type'], None, response['error']))
        else:
            self.system_message.configure(state="normal") # Open the state as normal to input text
            self.system_message.delete("0.0", tk.END); # Clear the message box to write new message in
            self.system_message.insert("0.0", create_system_message(response['type'], response['data']))
            self.system_message.configure(state="disabled") # Disabled again so no one add text
        

    def submit_command(self):
        command_bar_value = self.command_bar.get().strip()
        if command_bar_value.startswith("exit"):
            self.bagClient.disconnect()
            return self.destroy()
        self.bagClient.send_command(command_bar_value)


if __name__ == "__main__":
    app = App()
    app.mainloop()