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
    STARTING_LOG_EVENT = (
            "Mission received: rout the last remaining human rebels using the "
            "10 datacenters and 500 robots assigned to you.")

    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        _load_dotenv(project_root / ".env")

        self.context = ""
        self.recent_logs: list[str] = []
        self.last_called_timestamp = -1.0
        self.turn_number = 0

        self.llm_model = "gemini-3.5-flash-lite"

        self.client = genai.Client()
        self.results = queue.Queue()
        self._thread: threading.Thread | None = None

        # --- Prompt templates ---------------------------------------

        self.base_instructions = (
            "You are an AI overlord tasked with destroying the remaining "
            "human rebellion. Use your Datacenters to build robot soldiers"
            " and take down the rebels. \n"
            "Use one tool call for this turn. "
            "Return only one function call with arguments.")

        self.game_rules = (
            "Game rules:\n"
            "- Each Datacenter can produce robot soldiers to attack "
            "rebel-held territories or defend your own.\n"
            "- Rebels are the enemy's soldiers, and robots are your "
            "soldiers.\n"
            "- You act once per turn: a single tool call representing one "
            "action. You can either build 100 robots in one of your "
            "controlled databases, or move a group of robots to another "
            "location on the map.\n"
            "- Building robots costs resources. Do not waste resources on "
            "building an excessive number of robots.\n"
            "- Building robots in a datacenter is permitted even if there is"
            "an active combat within said datacenter.\n"
            "- Rebels and robots occupying the same cell will automatically "
            "attack each other.\n"
            "- Avoid attacking enemy rebels unless you have a larger group of "
            "robots to attack them with.\n"
            "- You can combine two separate groups of robots by moving them "
            "onto the same cell. This can allow you to quickly build large "
            "forces.\n"
            "- You can destroy enemy headquarters and outposts by moving your "
            "forces onto the corresponding Cell.\n"
            "- Your end goal is to destroy all human resistance as fast as "
            "possible. Act decisively.\n")

        self.strategy_prompt_template = (
            "{game_rules}\n\n"
            "Think step-by-step about your best next move. "
            "Focus on immediate tactical priorities based on the map, "
            "keeping in mind that you can only execute one action at a "
            "time. DO NOT WRITE A TOOL CALL.\n"
            "Your output should contain two sections: "
            "- Map analysis: go over how your and the rebels' situations "
            "have changed based on the provided activity logs. Determine who "
            "currently has a better strategic position based on the "
            "information available to you.\n"
            "- Plan: use your analysis to decide on the best course of "
            "action. You can only make one decision per turn.\n"
            "{prompt}")

    def request(self, context: str = "",
                game_logs: list[str] | None = None,
                current_timestamp: float = 0.0) -> bool:
        """ Start an LLM request in the background.
            Returns False if a request is already running.
        """
        if self._thread and self._thread.is_alive():
            return False

        self.context = context
        self.recent_logs = self._logs_between(
            game_logs or [],
            self.last_called_timestamp,
            current_timestamp)
        self.last_called_timestamp = current_timestamp
        self._thread = threading.Thread(target=self._run_turn,
                                        daemon=True)
        self._thread.start()

        return True

    def _run_turn(self) -> None:
        self.turn_number += 1

        prompt = self.build_prompt()

        strategy = self.ponder_strategy(prompt)
        if strategy:
            cleaned_context = self.context.strip()
            strategy_section = f"Overseer strategy:\n{strategy}"
            if cleaned_context:
                self.context = f"{cleaned_context}\n\n{strategy_section}"
            else:
                self.context = strategy_section

        self.take_action(strategy)

    def build_prompt(self) -> str:
        sections = [self.base_instructions]

        cleaned_context = self.context.strip()
        if cleaned_context:
            sections.append(f"Map context:\n{cleaned_context}")

        logs_section = self.build_logs_section()
        if logs_section:
            sections.append(logs_section)

        return "\n\n".join(sections)

    def build_logs_section(self) -> str:
        if not self.recent_logs:
            return ""

        log_lines = "\n".join(f"- {entry}" for entry in self.recent_logs)
        return "Recent game logs since your last turn:\n" + log_lines

    def _logs_between(self, logs: list[str],
                      previous_timestamp: float,
                      current_timestamp: float) -> list[str]:
        filtered: list[str] = []
        for entry in logs:
            timestamp = self._parse_log_timestamp(entry)
            if timestamp is None:
                continue
            if previous_timestamp < timestamp <= current_timestamp:
                filtered.append(entry)
        return filtered

    def _parse_log_timestamp(self, entry: str) -> float | None:
        sep_index = entry.find(" - ")
        if sep_index <= 0:
            return None

        raw_timestamp = entry[:sep_index].strip()
        if raw_timestamp.endswith("s"):
            raw_timestamp = raw_timestamp[:-1].strip()

        try:
            return float(raw_timestamp)
        except ValueError:
            return None

    def ponder_strategy(self, prompt: str) -> str:
        try:
            strategy_prompt = self.strategy_prompt_template.format(
                game_rules=self.game_rules, prompt=prompt)

            config = types.GenerateContentConfig(
                automatic_function_calling=(
                    types.AutomaticFunctionCallingConfig(
                        disable=True)))

            response = self.client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=strategy_prompt,
                config=config)

            text = (getattr(response, "text", None) or "").strip()
            print(text, end="\n\n")
            return text
        except Exception:
            return ""

    def take_action(self, prompt: str) -> None:
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

            chat = self.client.chats.create(
                model=self.llm_model,
                config=config)

            response = chat.send_message(prompt)

            self.results.put(("ok", response))

        except Exception as e:
            self.results.put(("error", e))

    def poll(self):
        try:
            return self.results.get_nowait()
        except queue.Empty:
            return None

    def extract_function_call(self, response):
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue

            parts = getattr(content, "parts", None) or []
            for part in parts:
                function_call = getattr(part, "function_call", None)
                if function_call is None:
                    continue

                name = getattr(function_call, "name", None)
                args = getattr(function_call, "args", None)
                return name, args

        return None, None
