import uuid

class DummyProvider:
    def charge(self, payment, payload):
        return str(uuid.uuid4())

    def verify_callback(self, request):
        return True, request.POST
