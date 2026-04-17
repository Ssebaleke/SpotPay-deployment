"""
freeradius.py
=============
Direct interface to FreeRADIUS MySQL database.
FreeRADIUS uses its own schema (radcheck, radreply, radusergroup, radgroupcheck, radgroupreply, nas, radacct).
This module reads/writes that schema directly — no REST API needed.
FreeRADIUS authenticates users by querying these tables in real time.
"""

import MySQLdb
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def _conn():
    """Open a connection to the FreeRADIUS MySQL database."""
    cfg = settings.FREERADIUS_DB
    return MySQLdb.connect(
        host=cfg["host"],
        port=cfg["port"],
        db=cfg["name"],
        user=cfg["user"],
        passwd=cfg["password"],
        connect_timeout=5,
    )


# ─── NAS (MikroTik Router) ────────────────────────────────────────────────────

def sync_nas(nas_device):
    """
    Insert or update a NAS entry in FreeRADIUS nas table.
    FreeRADIUS uses this to validate which routers can send auth requests.
    """
    try:
        db = _conn()
        cur = db.cursor()
        cur.execute("SELECT id FROM nas WHERE nasname = %s", (nas_device.nas_ip,))
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE nas SET shortname=%s, secret=%s, description=%s WHERE nasname=%s",
                (nas_device.name, nas_device.shared_secret, nas_device.description, nas_device.nas_ip)
            )
        else:
            cur.execute(
                "INSERT INTO nas (nasname, shortname, type, secret, description) VALUES (%s, %s, 'other', %s, %s)",
                (nas_device.nas_ip, nas_device.name, nas_device.shared_secret, nas_device.description)
            )
        db.commit()
        cur.close()
        db.close()
    except Exception as e:
        logger.error("sync_nas failed for %s: %s", nas_device.nas_ip, e)


def delete_nas(nas_ip):
    """Remove a NAS entry from FreeRADIUS."""
    try:
        db = _conn()
        cur = db.cursor()
        cur.execute("DELETE FROM nas WHERE nasname = %s", (nas_ip,))
        db.commit()
        cur.close()
        db.close()
    except Exception as e:
        logger.error("delete_nas failed for %s: %s", nas_ip, e)


# ─── Group (Profile) ──────────────────────────────────────────────────────────

def sync_profile(profile):
    """
    Write profile attributes to FreeRADIUS radgroupcheck and radgroupreply tables.
    Group name = vendor_id_profilename to keep vendor isolation.
    """
    group = _group_name(profile)
    try:
        db = _conn()
        cur = db.cursor()

        # Clear existing group attributes
        cur.execute("DELETE FROM radgroupcheck WHERE groupname = %s", (group,))
        cur.execute("DELETE FROM radgroupreply WHERE groupname = %s", (group,))

        # Auth-Type = Local (allow password check)
        cur.execute(
            "INSERT INTO radgroupcheck (groupname, attribute, op, value) VALUES (%s, 'Auth-Type', ':=', 'Local')",
            (group,)
        )

        # Simultaneous-Use
        cur.execute(
            "INSERT INTO radgroupcheck (groupname, attribute, op, value) VALUES (%s, 'Simultaneous-Use', ':=', %s)",
            (group, str(profile.simultaneous_use))
        )

        # Session-Timeout (seconds)
        if profile.session_timeout:
            cur.execute(
                "INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES (%s, 'Session-Timeout', ':=', %s)",
                (group, str(profile.session_timeout * 60))
            )

        # Data limit — MikroTik uses Mikrotik-Total-Limit (bytes)
        if profile.data_limit_mb:
            limit_bytes = profile.data_limit_mb * 1024 * 1024
            cur.execute(
                "INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES (%s, 'Mikrotik-Total-Limit', ':=', %s)",
                (group, str(limit_bytes))
            )

        # Speed limits — MikroTik rate limit format "upload/download"
        if profile.download_kbps or profile.upload_kbps:
            rate = f"{profile.upload_kbps}k/{profile.download_kbps}k"
            cur.execute(
                "INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES (%s, 'Mikrotik-Rate-Limit', ':=', %s)",
                (group, rate)
            )

        db.commit()
        cur.close()
        db.close()
    except Exception as e:
        logger.error("sync_profile failed for profile %s: %s", profile.id, e)


def delete_profile(profile):
    """Remove a profile group from FreeRADIUS."""
    group = _group_name(profile)
    try:
        db = _conn()
        cur = db.cursor()
        cur.execute("DELETE FROM radgroupcheck WHERE groupname = %s", (group,))
        cur.execute("DELETE FROM radgroupreply WHERE groupname = %s", (group,))
        db.commit()
        cur.close()
        db.close()
    except Exception as e:
        logger.error("delete_profile failed: %s", e)


# ─── Voucher (User) ───────────────────────────────────────────────────────────

def add_voucher(voucher):
    """
    Add a voucher as a FreeRADIUS user.
    - radcheck: username + password (Cleartext-Password)
    - radusergroup: links user to their profile group
    """
    group = _group_name(voucher.batch.profile)
    try:
        db = _conn()
        cur = db.cursor()

        # Password
        cur.execute("DELETE FROM radcheck WHERE username = %s", (voucher.code,))
        cur.execute(
            "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, 'Cleartext-Password', ':=', %s)",
            (voucher.code, voucher.code)
        )

        # Group membership
        cur.execute("DELETE FROM radusergroup WHERE username = %s", (voucher.code,))
        cur.execute(
            "INSERT INTO radusergroup (username, groupname, priority) VALUES (%s, %s, 1)",
            (voucher.code, group)
        )

        db.commit()
        cur.close()
        db.close()
    except Exception as e:
        logger.error("add_voucher failed for %s: %s", voucher.code, e)


def disable_voucher(code):
    """Disable a voucher by removing it from FreeRADIUS."""
    try:
        db = _conn()
        cur = db.cursor()
        cur.execute("DELETE FROM radcheck WHERE username = %s", (code,))
        cur.execute("DELETE FROM radusergroup WHERE username = %s", (code,))
        db.commit()
        cur.close()
        db.close()
    except Exception as e:
        logger.error("disable_voucher failed for %s: %s", code, e)


def bulk_add_vouchers(vouchers):
    """Add multiple vouchers in a single DB transaction — much faster than one by one."""
    if not vouchers:
        return

    group = _group_name(vouchers[0].batch.profile)
    try:
        db = _conn()
        cur = db.cursor()

        check_rows = [(v.code, "Cleartext-Password", ":=", v.code) for v in vouchers]
        group_rows = [(v.code, group, 1) for v in vouchers]

        cur.executemany(
            "INSERT IGNORE INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
            check_rows
        )
        cur.executemany(
            "INSERT IGNORE INTO radusergroup (username, groupname, priority) VALUES (%s, %s, %s)",
            group_rows
        )

        db.commit()
        cur.close()
        db.close()
    except Exception as e:
        logger.error("bulk_add_vouchers failed: %s", e)


# ─── Active Sessions ──────────────────────────────────────────────────────────

def get_active_sessions(vendor_usernames):
    """
    Pull active sessions from radacct for a vendor's voucher codes.
    Returns list of dicts.
    """
    if not vendor_usernames:
        return []
    try:
        db = _conn()
        cur = db.cursor()
        placeholders = ",".join(["%s"] * len(vendor_usernames))
        cur.execute(
            f"""
            SELECT username, nasipaddress, acctsessionid, framedipaddress,
                   calledstationid, callingstationid,
                   acctinputoctets, acctoutputoctets, acctsessiontime, acctstarttime
            FROM radacct
            WHERE acctstoptime IS NULL
            AND username IN ({placeholders})
            ORDER BY acctstarttime DESC
            """,
            vendor_usernames
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        db.close()
        return rows
    except Exception as e:
        logger.error("get_active_sessions failed: %s", e)
        return []


def get_session_history(vendor_usernames, limit=100):
    """Pull recent session history for a vendor's users."""
    if not vendor_usernames:
        return []
    try:
        db = _conn()
        cur = db.cursor()
        placeholders = ",".join(["%s"] * len(vendor_usernames))
        cur.execute(
            f"""
            SELECT username, nasipaddress, acctsessionid, framedipaddress,
                   acctinputoctets, acctoutputoctets, acctsessiontime,
                   acctstarttime, acctstoptime
            FROM radacct
            WHERE username IN ({placeholders})
            ORDER BY acctstarttime DESC
            LIMIT %s
            """,
            vendor_usernames + [limit]
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        db.close()
        return rows
    except Exception as e:
        logger.error("get_session_history failed: %s", e)
        return []


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _group_name(profile):
    """Unique group name per vendor to ensure isolation."""
    return f"v{profile.vendor_id}_{profile.name}".replace(" ", "_").lower()
