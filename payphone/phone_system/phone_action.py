

class PhoneAction:
    def __init__(self, action):
        self.action = action

    def __call__(self):
        return self.action()
