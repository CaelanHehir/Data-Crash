import os
import queue
import threading
from pathlib import Path

from google import genai
from google.genai import types

from src.overseer.overseer_tools import TOOLS


def _load_dotenv(dotenv_path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ."""
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        if line.startswith("export "):
            line = line[7:].strip()

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


class Overseer:
    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        _load_dotenv(project_root / ".env")

        self.context = ""
        self.client = genai.Client()
        self.results = queue.Queue()
        self._thread: threading.Thread | None = None

    def request(self, prompt: str) -> bool:
        """ Start an LLM request in the background.
            Returns False if a request is already running.
        """
        if self._thread and self._thread.is_alive():
            return False

        self._thread = threading.Thread(target=self._run, args=(prompt,),
                                        daemon=True)
        self._thread.start()

        return True

    def _run(self, prompt: str) -> None:
        try:
            config = types.GenerateContentConfig(
                tools=TOOLS,

                automatic_function_calling=(
                    types.AutomaticFunctionCallingConfig(
                        disable=True)),

                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="ANY")),
            )

            response = self.client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
                config=config)

            self.results.put(("ok", response))

        except Exception as e:
            self.results.put(("error", e))

    def poll(self):
        try:
            return self.results.get_nowait()
        except queue.Empty:
            return None
