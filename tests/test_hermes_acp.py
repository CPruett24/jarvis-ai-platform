from services.agents.hermes_acp import (
    HermesACPConnection,
)


def test_hermes_acp_finds_installed_executable(monkeypatch, tmp_path):
    from services.agents import hermes_acp

    executable = tmp_path / "hermes.exe"
    executable.touch()
    monkeypatch.setattr(hermes_acp.shutil, "which", lambda name: str(executable) if name == "hermes" else None)

    connection = HermesACPConnection()

    assert connection.executable == str(executable)
    assert connection.available is True


def test_hermes_acp_accepts_explicit_executable():

    connection = HermesACPConnection(
        executable="fake-hermes.exe"
    )

    assert (
        connection.executable
        == "fake-hermes.exe"
    )


def test_hermes_acp_context_manager():

    connection = HermesACPConnection(
        executable="fake-hermes.exe"
    )

    assert connection.process is None
    assert connection._reader_thread is None

def test_hermes_acp_missing_executable_is_unavailable(tmp_path):
    connection = HermesACPConnection(executable=str(tmp_path / "missing-hermes.exe"))
    assert connection.available is False
