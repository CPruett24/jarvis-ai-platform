import asyncio
import json
import os
import shutil
import subprocess
import threading
import uuid
import queue


class HermesACPError(Exception):
    """Raised when the Hermes ACP transport fails."""


class HermesACPConnection:
    """
    Lightweight ACP JSON-RPC client for the external Hermes process.

    JARVIS intentionally does not import Hermes' Python packages.
    Hermes runs in its own Python environment and communicates with
    JARVIS through the ACP stdio process boundary.
    """

    def __init__(
        self,
        executable=None,
        cwd=None,
    ):
        self.executable = (
            executable
            or shutil.which("hermes")
            or os.path.join(
                os.environ.get(
                    "LOCALAPPDATA",
                    "",
                ),
                "hermes",
                "bin",
                "hermes.exe",
            )
        )

        self.cwd = cwd

        self.process = None
        self._reader_thread = None
        self._stderr_thread = None
        self._reader_stop = threading.Event()

        self._pending = {}
        self._pending_lock = threading.Lock()

        self._notification_handlers = []

    @property
    def available(self):
        return bool(
            self.executable
            and os.path.isfile(
                self.executable
            )
        )

    def start(self):
        """
        Start the Hermes ACP server.
        """

        if self.process is not None:
            return

        if not self.available:
            raise HermesACPError(
                "Hermes executable was not found."
            )

        self.process = subprocess.Popen(
            [
                self.executable,
                "acp",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        self._reader_stop.clear()

        self._reader_thread = threading.Thread(
            target=self._read_stdout,
            name="hermes-acp-reader",
            daemon=True,
        )

        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name="hermes-acp-stderr",
            daemon=True,
        )

        self._reader_thread.start()
        self._stderr_thread.start()

        self._send_request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {},
                "clientInfo": {
                    "name": "JARVIS",
                    "version": "1.0",
                },
            },
        )

    def _read_stdout(self):
        """
        Read ACP JSON-RPC messages from Hermes stdout.

        Hermes reserves stdout exclusively for ACP transport.
        """

        if self.process is None:
            return

        stdout = self.process.stdout

        if stdout is None:
            return

        while not self._reader_stop.is_set():

            line = stdout.readline()

            if not line:
                break

            line = line.strip()

            if not line:
                continue

            try:
                message = json.loads(line)

            except json.JSONDecodeError:
                continue

            self._handle_message(
                message
            )

    def _read_stderr(self):
        """
        Consume Hermes stderr so the subprocess cannot block on a
        full stderr pipe.

        Hermes sends human-readable logs to stderr while ACP JSON-RPC
        messages remain on stdout.
        """

        if self.process is None:
            return

        stderr = self.process.stderr

        if stderr is None:
            return

        while not self._reader_stop.is_set():

            line = stderr.readline()

            if not line:
                break

            line = line.rstrip()

            if line:
                print(
                    f"[Hermes ACP] {line}"
                )

    def _handle_message(
        self,
        message,
    ):
        print(
            "[Hermes ACP RAW]",
            json.dumps(
                message,
                ensure_ascii=False,
            ),
            flush=True,
        )

        # ---------------------------------------------------------
        # JSON-RPC response to a JARVIS request
        # ---------------------------------------------------------
        message_id = message.get("id")

        if (
            message_id is not None
            and (
                "result" in message
                or "error" in message
            )
        ):

            with self._pending_lock:

                pending = self._pending.get(
                    message_id
                )

            if pending is None:
                return

            pending["response"] = message
            pending["event"].set()

            return

        # ---------------------------------------------------------
        # ACP notifications
        # ---------------------------------------------------------
        method = message.get(
            "method"
        )

        if method == "session/update":

            for handler in list(
                self._notification_handlers
            ):

                try:

                    handler(
                        message.get(
                            "params",
                            {},
                        )
                    )

                except Exception:
                    continue

            return

        # ---------------------------------------------------------
        # Agent -> JARVIS request
        # ---------------------------------------------------------
        if method:

            self._handle_server_request(
                message
            )

    def _handle_server_request(
        self,
        message,
    ):
        """
        Handle requests initiated by Hermes.

        ACP allows the agent to call back into the client,
        particularly for permission requests.
        """

        method = message.get(
            "method"
        )

        request_id = message.get(
            "id"
        )

        params = message.get(
            "params",
            {},
        )

        print(
            "[Hermes ACP REQUEST]",
            method,
            flush=True,
        )

        if method == "session/request_permission":

            self._send_permission_response(
                request_id
            )

            return

        # Unknown agent requests must receive an error
        # rather than leaving Hermes waiting indefinitely.

        self._send_jsonrpc_error(
            request_id,
            -32601,
            f"Unsupported ACP method: {method}",
        )

    def _send_permission_response(
        self,
        request_id,
    ):
        """
        Initial JARVIS permission policy.

        For now, deny permission requests rather than silently
        granting potentially dangerous terminal/file operations.

        We will replace this with JARVIS's actual permission
        system later.
        """

        self._write_jsonrpc(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "outcome": {
                        "outcome": "cancelled",
                    }
                },
            }
        )

    def _send_jsonrpc_error(
        self,
        request_id,
        code,
        message,
    ):
        self._write_jsonrpc(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": code,
                    "message": message,
                },
            }
        )

    def _write_jsonrpc(
        self,
        message,
    ):
        if self.process is None:
            return

        if self.process.stdin is None:
            return

        payload = (
            json.dumps(
                message,
                ensure_ascii=False,
            )
            + "\n"
        )

        try:

            self.process.stdin.write(
                payload
            )

            self.process.stdin.flush()

        except (
            BrokenPipeError,
            OSError,
        ):

            return

    def add_notification_handler(
        self,
        handler,
    ):
        self._notification_handlers.append(
            handler
        )

    def _send_request(
        self,
        method,
        params,
        timeout=30,
    ):
        if self.process is None:
            raise HermesACPError(
                "Hermes ACP is not running."
            )

        if (
            self.process.stdin is None
        ):
            raise HermesACPError(
                "Hermes ACP stdin is unavailable."
            )

        request_id = str(
            uuid.uuid4()
        )

        event = threading.Event()

        pending = {
            "event": event,
            "response": None,
        }

        with self._pending_lock:
            self._pending[
                request_id
            ] = pending

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        try:

            self.process.stdin.write(
                json.dumps(request)
                + "\n"
            )

            self.process.stdin.flush()

            if not event.wait(
                timeout
            ):
                raise HermesACPError(
                    f"Hermes ACP request timed out: "
                    f"{method}"
                )

            response = pending[
                "response"
            ]

            if response is None:
                raise HermesACPError(
                    "Hermes ACP closed without "
                    "returning a response."
                )

            if "error" in response:
                raise HermesACPError(
                    str(
                        response["error"]
                    )
                )

            return response.get(
                "result"
            )

        finally:

            with self._pending_lock:
                self._pending.pop(
                    request_id,
                    None,
                )

    def create_session(
        self,
        cwd=None,
    ):
        result = self._send_request(
            "session/new",
            {
                "cwd": (
                    cwd
                    or self.cwd
                    or os.getcwd()
                ),
                "mcpServers": [],
            },
        )

        if not result:
            raise HermesACPError(
                "Hermes ACP returned no "
                "session information."
            )

        return result[
            "sessionId"
        ]

    def stream_prompt(
        self,
        session_id,
        text,
        timeout=300,
    ):
        """
        Stream text chunks from an existing Hermes ACP session.
        """

        chunks = queue.Queue()
        finished = object()
        error_holder = []

        def collect_update(params):
            if params.get("sessionId") != session_id:
                return

            update = params.get(
                "update",
                {},
            )

            if update.get(
                "sessionUpdate"
            ) != "agent_message_chunk":
                return

            content = update.get(
                "content",
                {},
            )

            if content.get("type") != "text":
                return

            text_value = content.get(
                "text",
                "",
            )

            if text_value:
                chunks.put(text_value)

        def request_worker():
            try:
                self._send_request(
                    "session/prompt",
                    {
                        "sessionId": session_id,
                        "prompt": [
                            {
                                "type": "text",
                                "text": text,
                            }
                        ],
                    },
                    timeout=timeout,
                )

            except Exception as exc:
                error_holder.append(exc)

            finally:
                chunks.put(finished)

        self.add_notification_handler(
            collect_update
        )

        worker = threading.Thread(
            target=request_worker,
            name="hermes-acp-stream",
            daemon=True,
        )

        worker.start()

        try:
            while True:

                item = chunks.get()

                if item is finished:
                    break

                yield item

            if error_holder:
                raise error_holder[0]

        finally:

            try:
                self._notification_handlers.remove(
                    collect_update
                )

            except ValueError:
                pass    

    def prompt(
        self,
        session_id,
        text,
        timeout=300,
    ):
        """
        Send a prompt to an existing Hermes session.

        ACP emits session/update notifications while Hermes
        works. We collect final agent text from those events.
        """

        messages = []

        def collect_update(
            params
        ):
            if params.get(
                "sessionId"
            ) != session_id:
                return

            update = params.get(
                "update",
                {},
            )

            if update.get(
                "sessionUpdate"
            ) != "agent_message_chunk":
                return

            content = update.get(
                "content",
                {},
            )

            if content.get(
                "type"
            ) == "text":

                text_value = content.get(
                    "text",
                    "",
                )

                if text_value:
                    messages.append(
                        text_value
                    )

        self.add_notification_handler(
            collect_update
        )

        try:

            self._send_request(
                "session/prompt",
                {
                    "sessionId": session_id,
                    "prompt": [
                        {
                            "type": "text",
                            "text": text,
                        }
                    ],
                },
                timeout=timeout,
            )

        finally:

            try:
                self._notification_handlers.remove(
                    collect_update
                )

            except ValueError:
                pass

        return "".join(
            messages
        )

    def execute(
        self,
        task,
        cwd=None,
        timeout=300,
    ):
        """
        Execute one task through Hermes ACP.
        """

        self.start()

        session_id = self.create_session(
            cwd=cwd
        )

        response = self.prompt(
            session_id,
            task,
            timeout=timeout,
        )

        return {
            "success": True,
            "message": response,
            "session_id": session_id,
        }

    def close(self):
        self._reader_stop.set()

        process = self.process

        self.process = None

        if process is None:
            return

        if process.stdin is not None:

            try:
                process.stdin.close()

            except Exception:
                pass

        if process.poll() is None:

            process.terminate()

            try:
                process.wait(
                    timeout=5
                )

            except subprocess.TimeoutExpired:

                process.kill()
                process.wait()

        self._reader_thread = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        self.close()