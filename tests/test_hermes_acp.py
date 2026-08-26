from services.agents.hermes_acp import (
    HermesACPConnection,
)


def test_hermes_acp_finds_installed_executable():

    connection = HermesACPConnection()

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