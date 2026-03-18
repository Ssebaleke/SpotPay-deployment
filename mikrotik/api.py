import requests


def _session(router):
    s = requests.Session()
    s.auth = (router.api_username, router.api_password)
    s.timeout = 5
    return s


def _base(router):
    scheme = "https" if router.port == 443 else "http"
    return f"{scheme}://{router.host}:{router.port}/rest"


def test_connection(router):
    """Returns (True, None) or (False, error_str)."""
    try:
        r = _session(router).get(f"{_base(router)}/system/identity")
        if r.status_code == 200:
            return True, None
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)


def get_hotspot_profiles(router):
    """Returns list of profile dicts from MikroTik."""
    try:
        r = _session(router).get(f"{_base(router)}/ip/hotspot/user/profile")
        if r.status_code == 200:
            return r.json(), None
        return [], f"HTTP {r.status_code}"
    except Exception as e:
        return [], str(e)


def add_hotspot_user(router, username, profile_name, limit_uptime, limit_bytes_total=None):
    """Push a single voucher user to MikroTik hotspot."""
    payload = {
        "name": username,
        "password": username,
        "profile": profile_name,
        "limit-uptime": limit_uptime,
    }
    if limit_bytes_total:
        payload["limit-bytes-total"] = str(limit_bytes_total)
    try:
        r = _session(router).put(f"{_base(router)}/ip/hotspot/user", json=payload)
        if r.status_code in (200, 201):
            return True, None
        return False, r.text
    except Exception as e:
        return False, str(e)


def remove_hotspot_user(router, username):
    try:
        # find the .id first
        r = _session(router).get(
            f"{_base(router)}/ip/hotspot/user",
            params={"name": username}
        )
        if r.status_code != 200 or not r.json():
            return False, "User not found"
        uid = r.json()[0][".id"]
        d = _session(router).delete(f"{_base(router)}/ip/hotspot/user/{uid}")
        return d.status_code in (200, 204), d.text
    except Exception as e:
        return False, str(e)


def get_active_sessions(router):
    try:
        r = _session(router).get(f"{_base(router)}/ip/hotspot/active")
        if r.status_code == 200:
            return r.json(), None
        return [], f"HTTP {r.status_code}"
    except Exception as e:
        return [], str(e)
