import queue
import PhoneAction


class PhoneTree:
    def __init__(self, message, options: dict={}, action: PhoneAction=None, input_queue=None):
        self.message = message
        self.options = options if options else {}
        self.action = action
        self.input_queue = input_queue if input_queue else queue.Queue()

    def add_option(self, key, child_tree):
        self.options[key] = child_tree

    def update_input_queue(self, input_queue):
        self.input_queue = input_queue

    def play_audio(self):
        print(f"Playing audio: {self.message}")

    def execute_action(self):
        if self.action:
            return self.action()
        return True

    def listen_for_input(self):
        while True:
            user_input = input("Your choice: ")
            self.input_queue.put(user_input)

    def navigate(self, main_menu=None):
        self.play_audio()
        should_continue = self.execute_action()

        if not should_continue:
            print("Action returned False. Returning to main menu or ending call.")
            if main_menu:
                main_menu.navigate(main_menu)
            return

        if not self.options:
            print("No further options. Ending call or returning to main menu.")
            if main_menu:
                main_menu.navigate(main_menu)
            else:
                print("Ending call.")
            return

        while True:
            if not self.input_queue.empty():
                choice = self.input_queue.get()
                if choice in self.options:
                    next_node = self.options[choice]
                    next_node.update_input_queue(self.input_queue)
                    next_node.navigate(main_menu)
                    break
                else:
                    print("Invalid choice. Waiting for a valid option.")

