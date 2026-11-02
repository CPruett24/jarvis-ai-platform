"""Pure, testable loopback admission for the explicit C1 acceptance harness.

This is not an application network policy. The regression runner defaults to no
network and enables this only for an explicitly requested real-model session.
"""
from dataclasses import dataclass
import ipaddress
import re
import socket
from urllib.parse import urlsplit


@dataclass(frozen=True)
class OllamaLoopback:
    url: str
    address: str
    port: int

    @classmethod
    def configured(cls, value=None):
        raw = value or "http://127.0.0.1:11434"
        has_scheme = "://" in raw
        parsed = urlsplit(raw if has_scheme else "http://" + raw)
        if (parsed.scheme not in {"http", "https"} or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError("Real acceptance requires a direct local Ollama endpoint without credentials or URL paths.")
        host = parsed.hostname
        if host == "localhost":
            host = "127.0.0.1"  # Pin a numeric address; never resolve a hostname.
        if not host or "%" in host:
            raise ValueError("Ollama host must be a numeric loopback address or localhost.")
        address = ipaddress.ip_address(host)
        if not address.is_loopback or getattr(address, "ipv4_mapped", None):
            raise ValueError("Remote Ollama endpoints are forbidden in guarded acceptance.")
        port = parsed.port if parsed.port is not None else (11434 if not has_scheme else 443 if parsed.scheme == "https" else 80)
        if not 1 <= port <= 65535:
            raise ValueError("Invalid Ollama port.")
        host_text = f"[{address}]" if address.version == 6 else str(address)
        return cls(f"{parsed.scheme}://{host_text}:{port}", str(address), port)

    def permits(self, host, port):
        if not isinstance(host, str) or "%" in host or type(port) is not int:
            return False
        try:
            return ipaddress.ip_address(host) == ipaddress.ip_address(self.address) and port == self.port
        except ValueError:
            return False

    def audit_network(self, event, args):
        if event == "socket.connect":
            sock, destination = args
            allowed = (sock.family in {socket.AF_INET, socket.AF_INET6}
                       and sock.type == socket.SOCK_STREAM and isinstance(destination, tuple)
                       and len(destination) >= 2 and self.permits(destination[0], destination[1])
                       and (len(destination) < 4 or destination[3] == 0))
        elif event == "socket.getaddrinfo":
            host, port, family, kind, protocol = args
            allowed = (self.permits(host, port) and family in {0, socket.AF_INET, socket.AF_INET6}
                       and kind in {0, socket.SOCK_STREAM} and protocol in {0, socket.IPPROTO_TCP})
        else:
            allowed = False  # No UDP, DNS names, listening sockets, or other endpoints.
        if not allowed:
            raise AssertionError("C1 guard: only the pinned Ollama loopback endpoint is permitted")


def require_local_model(model, metadata):
    """Fail closed on cloud/remote stubs or unrecognized local-model metadata."""
    if (not isinstance(metadata, dict) or not isinstance(model, str) or re.search(r"(?:^|[-:])cloud(?:$|[-:])", model, re.I)
            or any(metadata.get(key) for key in ("remote_host", "remote_model"))
            or (metadata.get("details") or {}).get("format") != "gguf"
            or not (metadata.get("model_info") or metadata.get("modelinfo") or {}).get("general.architecture")):
        raise ValueError("Configured model is not verified as an installed local GGUF model; no model was changed or downloaded.")


def prepare_ollama_client(endpoint, model, client_factory):
    client = client_factory(host=endpoint.url, trust_env=False, follow_redirects=False, timeout=30.0)
    try:
        metadata = client.show(model)
        if hasattr(metadata, "model_dump"):
            metadata = metadata.model_dump(by_alias=True)
        require_local_model(model, metadata)
        return client
    except BaseException:
        client.close()
        raise
