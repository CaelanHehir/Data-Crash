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
    MAX_HISTORY_ENTRIES = 10

    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        _load_dotenv(project_root / ".env")

        self.context = ""
        self.previous_context = ""
        self.context_history: list[str] = []
        self.turn_number = 0

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
            "- You act once per turn: a single tool call representing one "
            "action. You can either build 100 robots in one of your "
            "controlled databases, or move a group of robots to another "
            "location on the map.\n"
            "- Building robots in a datacenter is permitted even if there is"
            "an active combat within said datacenter.\n"
            "- Rebels and robots occupying the same cell will automatically "
            "attack each other. Therefore, you do not need to manually direct "
            "robots to attack rebels residing in the same cell.\n"
            "- Avoid attacking enemy rebels unless you have a larger group of "
            "robots to attack them with.\n"
            "- You can combine two separate groups of robots by moving them "
            "onto the same cell. This can allow you to quickly build large "
            "forces.\n"
            "- Plan with the long game in mind: one action per turn means "
            "priorities should build toward a sustained advantage, not just "
            "an immediate gain.\n"
            "- However, if you have an overwhelming advantage, make sure to "
            "quickly capitalize on it to destroy the enemy without giving "
            "them time to resist.")

        self.summary_prompt_template = (
            "Compare the previous map state to the current map state "
            "below. Summarize what meaningfully changed in one or two "
            "short lines (e.g. units lost/gained, territory taken, "
            "new threats, player attacked a database).\n"
            "Previous map state:\n{previous}\n\n"
            "Current map state:\n{current}")

        self.strategy_prompt_template = (
            "{game_rules}\n\n"
            "Think step-by-step about your best next move. "
            "Focus on immediate tactical priorities based on the map, "
            "keeping in mind that you can only execute one action at a "
            "time."
            "Return plain text strategy notes only, no tool "
            "calls. Your output should contain two sections: "
            "A short map analysis where you go over the map state as your "
            "AI overlord character, and a plan section where you explain "
            "your next move. Keep roleplay to a minimum.\n\n"
            "{prompt}")

    def request(self, context: str = "") -> bool:
        """ Start an LLM request in the background.
            Returns False if a request is already running.
        """
        if self._thread and self._thread.is_alive():
            return False

        self.context = context
        self._thread = threading.Thread(target=self._run_turn,
                                        daemon=True)
        self._thread.start()

        return True

    def _run_turn(self) -> None:
        self.turn_number += 1

        # Snapshot the raw incoming map state before build_prompt/ponder
        # mutate self.context by appending strategy notes to it.
        current_map_state = self.context.strip()

        if self.previous_context:
            change_summary = self.summarize_changes(
                self.previous_context, current_map_state)
            if change_summary:
                self.context_history.append(
                    f"Turn {self.turn_number}: {change_summary}")
                if len(self.context_history) > self.MAX_HISTORY_ENTRIES:
                    self.context_history = (
                        self.context_history[-self.MAX_HISTORY_ENTRIES:])

        prompt = self.build_prompt()

        strategy = self.ponder_strategy(prompt)
        if strategy:
            cleaned_context = self.context.strip()
            strategy_section = f"Overseer strategy:\n{strategy}"
            if cleaned_context:
                self.context = f"{cleaned_context}\n\n{strategy_section}"
            else:
                self.context = strategy_section

        prompt = self.context
        self.take_action(prompt)

        # Remember this turn's raw map state (not the strategy-augmented
        # version) so the next turn compares apples to apples.
        self.previous_context = current_map_state

    def build_prompt(self) -> str:
        sections = [self.base_instructions]

        history_section = self.build_history_section()
        if history_section:
            sections.append(history_section)

        cleaned_context = self.context.strip()
        if cleaned_context:
            sections.append(f"Map context:\n{cleaned_context}")

        return "\n\n".join(sections)

    def build_history_section(self) -> str:
        if not self.context_history:
            return ""

        history_lines = "\n".join(
            f"- {entry}" for entry in self.context_history)
        return f"Context history (how the map has evolved):\n{history_lines}"

    def summarize_changes(self, previous: str, current: str) -> str:
        """ Ask the LLM to summarize what changed between two map states
            in one or two lines. Returns "" if nothing relevant changed
            or on failure.
        """
        if previous.strip() == current.strip():
            return ""

        try:
            summary_prompt = self.summary_prompt_template.format(
                previous=previous, current=current)

            config = types.GenerateContentConfig(
                automatic_function_calling=(
                    types.AutomaticFunctionCallingConfig(
                        disable=True)))

            response = self.client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=summary_prompt,
                config=config)

            text = (getattr(response, "text", None) or "").strip()
            print(text, end="\n\n")

            if not text or text.upper() == "NONE":
                return ""

            return text
        except Exception:
            return ""

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
                model="gemini-3.5-flash-lite",
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
