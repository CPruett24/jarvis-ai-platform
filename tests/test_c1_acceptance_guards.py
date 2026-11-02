from types import SimpleNamespace
import socket
import pytest

from scripts.c1_acceptance_guard import OllamaLoopback, require_local_model, prepare_ollama_client


@pytest.mark.parametrize("url", [
    "http://example.com:11434", "http://192.168.1.2:11434", "http://0.0.0.0:11434",
    "http://[::]:11434", "http://[::ffff:127.0.0.1]:11434", "http://user:pass@localhost:11434",
    "http://localhost:11434/proxy", "http://localhost:11434?next=evil", "ftp://127.0.0.1:11434",
    "http://127.0.0.1:0", "http://127.0.0.1:65536", "http://localhost.evil:11434",
])
def test_remote_or_ambiguous_endpoints_are_rejected(url):
    with pytest.raises(ValueError):
        OllamaLoopback.configured(url)


@pytest.mark.parametrize("configured,expected", [
    (None, "http://127.0.0.1:11434"), ("localhost:11434", "http://127.0.0.1:11434"),
    ("http://127.0.0.1:12345", "http://127.0.0.1:12345"),
    ("http://[::1]:11434", "http://[::1]:11434"),
])
def test_endpoint_is_numeric_and_pinned(configured, expected):
    policy = OllamaLoopback.configured(configured)
    assert policy.url == expected
    assert policy.permits(policy.address, policy.port)
    assert not policy.permits(policy.address, policy.port + 1)
    assert not policy.permits("localhost", policy.port)
    assert not policy.permits("8.8.8.8", policy.port)


def test_audit_allows_only_exact_tcp_destination_without_opening_sockets():
    policy = OllamaLoopback.configured()
    sock = SimpleNamespace(family=socket.AF_INET, type=socket.SOCK_STREAM)
    policy.audit_network("socket.connect", (sock, ("127.0.0.1", 11434)))
    policy.audit_network("socket.getaddrinfo", ("127.0.0.1", 11434, 0, socket.SOCK_STREAM, 0))
    for event, args in [
        ("socket.connect", (sock, ("127.0.0.1", 80))),
        ("socket.connect", (sock, ("127.0.0.2", 11434))),
        ("socket.connect", (sock, ("8.8.8.8", 11434))),
        ("socket.connect", (SimpleNamespace(family=socket.AF_INET, type=socket.SOCK_DGRAM), ("127.0.0.1", 11434))),
        ("socket.getaddrinfo", ("example.com", 11434, 0, socket.SOCK_STREAM, 0)),
        ("socket.sendto", (sock, "data", ("127.0.0.1", 11434))),
        ("socket.bind", (sock, ("127.0.0.1", 11434))),
    ]:
        with pytest.raises(AssertionError):
            policy.audit_network(event, args)


def test_cloud_or_unverified_models_fail_closed():
    local = {"details": {"format": "gguf"}, "model_info": {"general.architecture": "llama"}}
    require_local_model("configured-model", local)
    for name, metadata in [("model-cloud", local), ("model", {}), ("model", {**local, "remote_host": "remote"}),
                           ("model", {"details": None}), ("model", None)]:
        with pytest.raises(ValueError):
            require_local_model(name, metadata)


def test_real_client_disables_proxies_redirects_and_preserves_model_without_calls():
    calls = []
    client = SimpleNamespace(show=lambda model: calls.append(("show", model)) or
        {"details": {"format": "gguf"}, "model_info": {"general.architecture": "llama"}},
        close=lambda: calls.append(("close",)))
    def factory(**kwargs):
        calls.append(kwargs)
        return client
    assert prepare_ollama_client(OllamaLoopback.configured(), "existing-model", factory) is client
    assert calls == [{"host": "http://127.0.0.1:11434", "trust_env": False, "follow_redirects": False, "timeout": 30.0},
                     ("show", "existing-model")]


def test_failed_model_preflight_closes_client():
    calls = []
    client = SimpleNamespace(show=lambda model: {}, close=lambda: calls.append("closed"))
    with pytest.raises(ValueError):
        prepare_ollama_client(OllamaLoopback.configured(), "existing", lambda **kwargs: client)
    assert calls == ["closed"]


def test_fake_real_mode_wiring_uses_fixture_only_and_restores_state(monkeypatch):
    import json
    import ollama
    from scripts import accept_c1
    from services import ai_service, project_access
    from commands import router
    original_model, original_chat = ai_service.OLLAMA_MODEL, ai_service.chat
    original_projects = project_access._projects.copy()
    observed = []
    class Client:
        def __init__(self, **kwargs):
            observed.append(kwargs)
        def show(self, model):
            assert model == original_model
            return {"details": {"format": "gguf"}, "model_info": {"general.architecture": "llama"}}
        def chat(self, **kwargs):
            assert kwargs["model"] == original_model
            assert list(project_access._projects) == ["acceptance"]
            sources = json.loads(kwargs["messages"][-1]["content"])["observed_excerpts"]
            return {"message": {"content": "Fixture interpretation [" + sources[0]["source_id"] + "]"}}
        def close(self):
            observed.append("closed")
    monkeypatch.setattr(ollama, "Client", Client)
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    assert accept_c1.main(real_ollama=True, enable_loopback=lambda endpoint: observed.append(endpoint.url)) == 0
    assert ai_service.chat is original_chat and ai_service.OLLAMA_MODEL == original_model
    assert project_access._projects == original_projects
    assert "closed" in observed


def test_runner_retains_storage_and_process_guards_when_loopback_is_enabled():
    import runpy
    from pathlib import Path
    namespace = runpy.run_path(str(Path(__file__).with_name("run_c1_regressions.py")))
    audit = namespace["audit"]
    sock = SimpleNamespace(family=socket.AF_INET, type=socket.SOCK_STREAM)
    with pytest.raises(AssertionError):
        audit("socket.connect", (sock, ("127.0.0.1", 11434)))  # default stays offline
    audit.__globals__["OLLAMA_LOOPBACK"] = OllamaLoopback.configured()
    audit("socket.connect", (sock, ("127.0.0.1", 11434)))  # policy check only; no socket operation
    for event, args in [
        ("socket.connect", (sock, ("8.8.8.8", 11434))),
        ("subprocess.Popen", ("not-started", [], None, None)),
        ("os.startfile", ("not-opened",)),
        ("sqlite3.connect", ("data/not-opened.db",)),
        ("open", ("data/not-opened.db", "rb", 0)),
        ("open", ("data/status.json", "w", 0)),
        ("open", (".env", "w", 0)),
    ]:
        with pytest.raises(AssertionError):
            audit(event, args)
