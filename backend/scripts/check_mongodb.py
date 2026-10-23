"""Safe MongoDB connectivity diagnostic.

Reports *why* a connection fails without ever printing the URI, username,
password or any other secret.

Usage (from the ``backend`` directory):

    python scripts/check_mongodb.py

Exit codes:
    0 - ping succeeded
    1 - configuration missing
    2 - DNS / network / Atlas access-list problem
    3 - authentication or other driver error
"""

from __future__ import annotations

import asyncio
import socket
import ssl
import sys
from urllib.parse import urlparse

from pymongo import AsyncMongoClient
from pymongo.errors import (
    ConfigurationError,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)

from app.core.config import get_settings


def _extract_host(uri: str) -> str | None:
    """Return only the hostname from a MongoDB URI (never credentials)."""
    try:
        # Normalise the scheme so urlparse can handle both forms.
        parsed = urlparse(uri)
        host = parsed.hostname
        if host:
            return host
        # mongodb+srv://user:pass@host/... -> urlparse handles this fine
        return None
    except Exception:
        return None


def _check_dns(host: str, srv: bool = False) -> tuple[bool, str]:
    try:
        if srv:
            # MongoDB Atlas SRV clusters have no A/AAAA record on the cluster
            # hostname itself - the addresses live in the SRV record.
            import dns.resolver

            answers = dns.resolver.resolve(f"_mongodb._tcp.{host}", "SRV")
            targets = sorted({str(r.target).rstrip(".") for r in answers})
            if not targets:
                return False, "SRV record returned no targets"
            return True, f"SRV resolved to {len(targets)} shard host(s)"
        infos = socket.getaddrinfo(host, None)
        addresses = {info[4][0] for info in infos}
        return True, f"resolved to {len(addresses)} address(es)"
    except Exception as exc:
        name = type(exc).__name__
        if name == "NXDOMAIN":
            return False, "SRV record does not exist (check the cluster hostname)"
        if name in {"NoAnswer", "NoNameservers", "Timeout", "LifetimeTimeout"}:
            return False, f"DNS SRV lookup failed ({name})"
        return False, f"DNS lookup error ({name})"


def _check_tls(host: str) -> tuple[bool, str]:
    """Perform a raw TLS handshake against the MongoDB port.

    This distinguishes a *TLS* failure (Atlas rejecting the client, usually a
    network/egress or TLS-inspection problem) from an authentication failure
    or a plain timeout.
    """
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 27017), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as wrapped:
                return True, f"TLS handshake OK ({wrapped.version()})"
    except ssl.SSLError as exc:
        reason = getattr(exc, "reason", "") or type(exc).__name__
        return False, f"TLS handshake rejected by server ({reason})"
    except socket.timeout:
        return False, "TCP/TLS connection timed out on port 27017"
    except OSError as exc:
        return False, f"TCP connection failed ({type(exc).__name__})"


async def main() -> int:
    settings = get_settings()

    if not settings.mongodb_uri:
        print("STATUS: configuration missing")
        print("  MONGODB_URI is empty in backend/.env or the project-root .env.")
        print("  Configure MONGODB_URI with your Atlas connection string.")
        return 1

    host = _extract_host(settings.mongodb_uri)
    print(f"Database name: {settings.mongodb_db_name}")
    print(f"Cluster host:  {host or 'unknown'}")

    if host:
        is_srv = settings.mongodb_uri.startswith("mongodb+srv://")
        ok, detail = _check_dns(host, srv=is_srv)
        print(f"DNS:           {'OK' if ok else 'FAIL'} - {detail}")
        if not ok:
            print("STATUS: DNS cannot resolve the Atlas cluster SRV record.")
            print("  Check your network/DNS/VPN. Atlas SRV clusters need working DNS.")
            return 2

        # Probe TLS on the actual shard host(s) so a TLS rejection is reported
        # as such instead of a generic "server selection timeout".
        shard_hosts: list[str] = []
        try:
            if is_srv:
                import dns.resolver

                answers = dns.resolver.resolve(f"_mongodb._tcp.{host}", "SRV")
                shard_hosts = sorted({str(r.target).rstrip(".") for r in answers})
            else:
                shard_hosts = [host]
        except Exception:
            shard_hosts = []

        if shard_hosts:
            tls_expected = is_srv or "tls=true" in settings.mongodb_uri.lower()
            if not tls_expected:
                print("TLS (27017):   skipped - URI does not require TLS")
                shard_hosts = []
        if shard_hosts:
            ok, detail = _check_tls(shard_hosts[0])
            print(f"TLS (27017):   {'OK' if ok else 'FAIL'} - {detail}")
            if not ok and "rejected by server" in detail:
                print("STATUS: Atlas rejected the TLS handshake.")
                print("  This is almost always one of:")
                print("   - the current public IP is not on the Atlas IP access list")
                print("   - the cluster is paused")
                print("   - a corporate proxy / antivirus / NAT64 gateway is")
                print("     interfering with outbound TLS")
                return 2

        # A TLS check only makes sense for SRV/443, but it is a useful signal.
        if settings.mongodb_uri.startswith("mongodb+srv://"):
            ok, detail = _check_tls(host)
            print(f"TLS (443):     {'OK' if ok else 'FAIL'} - {detail}")

    client: AsyncMongoClient | None = None
    try:
        client = AsyncMongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=min(settings.mongodb_timeout_ms, 8000),
            connectTimeoutMS=min(settings.mongodb_timeout_ms, 8000),
            appname="agrivision-ai-diagnostic",
        )
        await client.admin.command("ping")
        print("PING:          OK")
        print("STATUS: MongoDB connection succeeded.")
        return 0
    except ServerSelectionTimeoutError as exc:
        text = str(exc).lower()
        print("PING:          FAIL - ServerSelectionTimeoutError")
        if "authentication" in text:
            print("STATUS: authentication failure (check the database user credentials).")
            return 3
        print("STATUS: server selection timeout.")
        print("  Likely causes: Atlas IP access list does not include this machine,")
        print("  outbound port 27017 is blocked, or the cluster is paused.")
        return 2
    except OperationFailure as exc:
        print("PING:          FAIL - OperationFailure")
        if "auth" in str(exc).lower():
            print("STATUS: authentication failure (check the database user credentials).")
        else:
            print(f"STATUS: operation rejected ({exc.code if hasattr(exc, 'code') else 'unknown'}).")
        return 3
    except ConfigurationError as exc:
        print("PING:          FAIL - ConfigurationError")
        print(f"STATUS: invalid MongoDB URI format ({type(exc).__name__}).")
        return 3
    except PyMongoError as exc:
        print(f"PING:          FAIL - {type(exc).__name__}")
        print("STATUS: MongoDB driver error. See backend logs for a safe description.")
        return 3
    finally:
        if client is not None:
            await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
