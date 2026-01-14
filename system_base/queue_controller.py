class QueueController:
    def __init__(self, limit_n):
        self.limit_n = limit_n
        self.current_training = 0

    def request_permission(self):
        if self.current_training < self.limit_n:
            self.current_training += 1
            return True
        return False

    def release(self):
        self.current_training = max(0, self.current_training - 1)