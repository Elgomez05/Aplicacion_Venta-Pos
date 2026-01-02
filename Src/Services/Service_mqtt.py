class DummyMQTT:
    def newsession(self, *args, **kwargs):
        return None

    def publish(self, *args, **kwargs):
        return None

    def subscribe(self, *args, **kwargs):
        return None

    def close(self):
        return None
