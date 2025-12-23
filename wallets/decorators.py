from django.shortcuts import redirect
from django.utils import timezone

WALLET_TIMEOUT = 900  # 15 minutes

def wallet_required(view_func):
    def wrapper(request, *args, **kwargs):
        auth_time = request.session.get('wallet_auth_time')

        if not auth_time:
            return redirect('wallet_authenticate')

        elapsed = timezone.now().timestamp() - auth_time

        if elapsed > WALLET_TIMEOUT:
            request.session.pop('wallet_authenticated', None)
            request.session.pop('wallet_auth_time', None)
            request.session.pop('wallet_otp_verified', None)
            return redirect('wallet_authenticate')

        return view_func(request, *args, **kwargs)

    return wrapper
