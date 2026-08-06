"""Turn a vless:// subscription link into an Xray client config.

Used by scripts/test_renewal_burn.py to push real traffic through a real
server config. Supports the shapes this panel actually hands out: reality/tls
over tcp, ws and grpc.
"""

import json
import urllib.parse as up


def parse_vless(link: str) -> dict:
    """Split a vless:// link into the pieces an outbound needs."""
    if not link.startswith("vless://"):
        raise ValueError("not a vless:// link")
    u = up.urlparse(link)
    return {
        "uuid": up.unquote(u.username or ""),
        "host": u.hostname,
        "port": u.port or 443,
        "tag": up.unquote(u.fragment or ""),
        "params": dict(up.parse_qsl(u.query)),
    }


def build_config(link: str, socks_port: int) -> dict:
    """A minimal Xray config: SOCKS in on localhost, this server out.

    The inbound listens on 127.0.0.1 only, so nothing on the network can use
    it and the host's own routing is untouched.
    """
    v = parse_vless(link)
    p = v["params"]
    net = p.get("type", "tcp")
    sec = p.get("security", "none")

    stream: dict = {"network": net, "security": sec}

    if sec == "reality":
        stream["realitySettings"] = {
            "serverName": p.get("sni", ""),
            "fingerprint": p.get("fp", "chrome"),
            "publicKey": p.get("pbk", ""),
            "shortId": p.get("sid", ""),
            "spiderX": p.get("spx", ""),
        }
    elif sec == "tls":
        tls: dict = {
            "serverName": p.get("sni") or p.get("host") or v["host"],
            "fingerprint": p.get("fp", "chrome"),
            "allowInsecure": False,
        }
        if p.get("alpn"):
            tls["alpn"] = p["alpn"].split(",")
        stream["tlsSettings"] = tls

    if net == "ws":
        stream["wsSettings"] = {
            "path": p.get("path", "/"),
            "headers": {"Host": p.get("host") or p.get("sni") or v["host"]},
        }
    elif net == "grpc":
        stream["grpcSettings"] = {"serviceName": p.get("serviceName", "")}
    elif net == "tcp" and p.get("headerType") == "http":
        stream["tcpSettings"] = {
            "header": {"type": "http", "request": {"headers": {"Host": [p.get("host", "")]}}}
        }

    user: dict = {"id": v["uuid"], "encryption": "none"}
    if p.get("flow"):
        user["flow"] = p["flow"]

    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "socks-in",
                "listen": "127.0.0.1",  # localhost only - never exposed
                "port": socks_port,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": False},
            }
        ],
        "outbounds": [
            {
                "tag": "proxy",
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {"address": v["host"], "port": v["port"], "users": [user]}
                    ]
                },
                "streamSettings": stream,
            }
        ],
    }


def write_config(link: str, socks_port: int, path: str) -> dict:
    cfg = build_config(link, socks_port)
    with open(path, "w") as fh:
        json.dump(cfg, fh, indent=2)
    return cfg
