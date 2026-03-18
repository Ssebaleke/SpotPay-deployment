"""
MikroTik API client — supports both protocols:
  - Binary API via librouteros  → port 8728 (plain) / 8729 (SSL)  — RouterOS v6 + v7
  - REST API via requests        → port 80 / 443 / custom          — RouterOS v7 only

api_mode is stored on the RouterConnection model after test_connection().
All public functions accept a router object and dispatch to the right protocol.
"""
import requests
import librouteros
from librouteros import connect as ros_connect
from librouteros.exceptions import TrapError, FatalError


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _is_binary_port(port):
    return port in (8728, 8729)


def _rest_session(router):
    s = requests.Session()
    s.auth = (router.api_username, router.api_password)
    s.timeout = 8
    return s


def _rest_base(router):
    scheme = "https" if router.port in (443, 8729) else "http"
    return f"{scheme}://{router.host}:{router.port}/rest"


def _binary_connect(router):
    """Open a librouteros connection. Caller must close it."""
    use_ssl = router.port == 8729
    return ros_connect(
        host=router.host,
        username=router.api_username,
        password=router.api_password,
        port=router.port,
        ssl_wrapper=librouteros.create_ssl_context() if use_ssl else None,
    )


# ─── Connection Test ──────────────────────────────────────────────────────────

def test_connection(router):
    """
    Try binary API first (works on v6+v7), fall back to REST (v7 only).
    Returns (True, None) or (False, error_str).
    Updates router.api_mode with what worked.
    """
    # Always try binary on port 8728/8729; also try binary on other ports
    # because some admins run API on non-standard ports.
    try:
        api = _binary_connect(router)
        list(api(cmd="/system/identity/print"))
        api.close()
        router.api_mode = "binary"
        return True, None
    except Exception as bin_err:
        pass

    # Fall back to REST
    try:
        r = _rest_session(router).get(f"{_rest_base(router)}/system/identity")
        if r.status_code == 200:
            router.api_mode = "rest"
            return True, None
        return False, f"REST HTTP {r.status_code}"
    except Exception as rest_err:
        return False, f"Binary: {bin_err} | REST: {rest_err}"


# ─── Get Hotspot Profiles ─────────────────────────────────────────────────────

def get_hotspot_profiles(router):
    """Returns (list_of_profile_dicts, error_or_None)."""
    if router.api_mode == "rest":
        try:
            r = _rest_session(router).get(f"{_rest_base(router)}/ip/hotspot/user/profile")
            if r.status_code == 200:
                return r.json(), None
            return [], f"HTTP {r.status_code}"
        except Exception as e:
            return [], str(e)
    else:
        try:
            api = _binary_connect(router)
            profiles = list(api(cmd="/ip/hotspot/user/profile/print"))
            api.close()
            return profiles, None
        except Exception as e:
            return [], str(e)


# ─── Add Hotspot User ─────────────────────────────────────────────────────────

def add_hotspot_user(router, username, profile_name, limit_uptime, limit_bytes_total=None, shared_users=1):
    """Push a voucher user to MikroTik and verify it was created."""
    if router.api_mode == "rest":
        return _rest_add_user(router, username, profile_name, limit_uptime, limit_bytes_total, shared_users)
    else:
        return _binary_add_user(router, username, profile_name, limit_uptime, limit_bytes_total, shared_users)


def _rest_add_user(router, username, profile_name, limit_uptime, limit_bytes_total, shared_users):
    payload = {
        "name": username,
        "password": username,
        "profile": profile_name,
        "limit-uptime": limit_uptime,
        "limit-bytes-total": str(limit_bytes_total) if limit_bytes_total else "0",
        "shared-users": str(shared_users),
    }
    try:
        r = _rest_session(router).put(f"{_rest_base(router)}/ip/hotspot/user", json=payload)
        if r.status_code not in (200, 201):
            return False, r.text
        return verify_hotspot_user(router, username)
    except Exception as e:
        return False, str(e)


def _binary_add_user(router, username, profile_name, limit_uptime, limit_bytes_total, shared_users):
    try:
        api = _binary_connect(router)
        params = {
            "name": username,
            "password": username,
            "profile": profile_name,
            "limit-uptime": limit_uptime,
            "limit-bytes-total": str(limit_bytes_total) if limit_bytes_total else "0",
            "shared-users": str(shared_users),
        }
        api(cmd="/ip/hotspot/user/add", **params)
        api.close()
        return verify_hotspot_user(router, username)
    except TrapError as e:
        return False, f"MikroTik error: {e}"
    except Exception as e:
        return False, str(e)


# ─── Verify Hotspot User ──────────────────────────────────────────────────────

def verify_hotspot_user(router, username):
    """Confirm user exists on router and is not disabled."""
    if router.api_mode == "rest":
        try:
            r = _rest_session(router).get(
                f"{_rest_base(router)}/ip/hotspot/user",
                params={"name": username}
            )
            if r.status_code != 200:
                return False, f"Verify HTTP {r.status_code}"
            data = r.json()
            if not data:
                return False, "User not found on router after push"
            if data[0].get("disabled", "false") == "true":
                return False, "User created but is disabled on router"
            return True, None
        except Exception as e:
            return False, str(e)
    else:
        try:
            api = _binary_connect(router)
            results = list(api(cmd="/ip/hotspot/user/print", **{"?name": username}))
            api.close()
            if not results:
                return False, "User not found on router after push"
            if results[0].get("disabled", "false") == "true":
                return False, "User created but is disabled on router"
            return True, None
        except Exception as e:
            return False, str(e)


# ─── Remove Hotspot User ──────────────────────────────────────────────────────

def remove_hotspot_user(router, username):
    if router.api_mode == "rest":
        try:
            r = _rest_session(router).get(
                f"{_rest_base(router)}/ip/hotspot/user",
                params={"name": username}
            )
            if r.status_code != 200 or not r.json():
                return False, "User not found"
            uid = r.json()[0][".id"]
            d = _rest_session(router).delete(f"{_rest_base(router)}/ip/hotspot/user/{uid}")
            return d.status_code in (200, 204), d.text
        except Exception as e:
            return False, str(e)
    else:
        try:
            api = _binary_connect(router)
            results = list(api(cmd="/ip/hotspot/user/print", **{"?name": username}))
            if not results:
                api.close()
                return False, "User not found"
            uid = results[0][".id"]
            api(cmd="/ip/hotspot/user/remove", **{".id": uid})
            api.close()
            return True, None
        except TrapError as e:
            return False, f"MikroTik error: {e}"
        except Exception as e:
            return False, str(e)


# ─── Active Sessions ──────────────────────────────────────────────────────────

def get_active_sessions(router):
    if router.api_mode == "rest":
        try:
            r = _rest_session(router).get(f"{_rest_base(router)}/ip/hotspot/active")
            if r.status_code == 200:
                return r.json(), None
            return [], f"HTTP {r.status_code}"
        except Exception as e:
            return [], str(e)
    else:
        try:
            api = _binary_connect(router)
            sessions = list(api(cmd="/ip/hotspot/active/print"))
            api.close()
            return sessions, None
        except Exception as e:
            return [], str(e)
