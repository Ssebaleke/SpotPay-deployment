class BasePaymentProvider:
    def charge(self, payment, payload):
        raise NotImplementedError

    def verify_callback(self, request):
        raise NotImplementedError
