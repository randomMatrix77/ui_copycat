from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from textwrap import dedent
from typing import Any

import google.generativeai as genai
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_experimental.tools import PythonREPLTool
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "stripe_assets"
VIDEO_PATH = ASSETS_DIR / "hover_change.mp4"
FRONTEND_DIR = PROJECT_ROOT / "generated-page"
GENERATED_COMPONENT_DIR = FRONTEND_DIR / "src" / "generated"
OUTPUT_COMPONENT = GENERATED_COMPONENT_DIR / "GeneratedMegaMenu.jsx"
MODEL_NAME = "gemini-3-flash-preview"
VIDEO_POLL_INTERVAL_SECONDS = 5
FINAL_RESPONSE_OUTPUT = PROJECT_ROOT / "generate_agent_response.md"
GREP_OUTPUT_LIMIT = 2_000
REPL_OUTPUT_LIMIT = 10_000
REPL_GUARDRAIL_MESSAGE = (
    "Error: Output exceeded 10,000 characters. Context window protected. "
    "Please use grep(filepath, pattern) or read_slice(filepath, start, end) "
    "to extract only the specific lines you need."
)


def get_api_key() -> str:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing API key. Set GOOGLE_API_KEY or GEMINI_API_KEY before running generate_agent.py."
        )
    return api_key


def ensure_assets() -> None:
    if not ASSETS_DIR.exists():
        raise FileNotFoundError(f"Missing assets directory: {ASSETS_DIR}")
    if not VIDEO_PATH.exists():
        raise FileNotFoundError(f"Missing video file: {VIDEO_PATH}")


def asset_inventory_text() -> str:
    files = sorted(path.relative_to(PROJECT_ROOT).as_posix() for path in ASSETS_DIR.rglob("*") if path.is_file())
    if not files:
        raise RuntimeError("stripe_assets/ is empty.")
    return "\n".join(f"- {item}" for item in files)


def ensure_output_dir() -> None:
    GENERATED_COMPONENT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_user_path(filepath: str) -> Path:
    candidate = Path(filepath)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


def grep(filepath: str, pattern: str) -> str:
    try:
        target = resolve_user_path(filepath)
        regex = re.compile(pattern)
    except re.error as exc:
        return f"Error: Invalid regex pattern: {exc}"
    except Exception as exc:
        return f"Error: Could not resolve path {filepath!r}: {exc}"

    if not target.exists():
        return f"Error: File not found: {filepath}"
    if not target.is_file():
        return f"Error: Not a file: {filepath}"

    matches: list[str] = []
    try:
        with target.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if regex.search(line):
                    matches.append(f"{line_number}: {line.rstrip()}")
    except OSError as exc:
        return f"Error: Could not read {filepath}: {exc}"

    if not matches:
        return "No matches found."

    output = "\n".join(matches)
    if len(output) > GREP_OUTPUT_LIMIT:
        return output[:GREP_OUTPUT_LIMIT] + "\n...[truncated]"
    return output


def read_slice(filepath: str, start_line: int, end_line: int) -> str:
    if start_line < 1 or end_line < start_line:
        return "Error: Invalid line range."

    try:
        target = resolve_user_path(filepath)
    except Exception as exc:
        return f"Error: Could not resolve path {filepath!r}: {exc}"

    if not target.exists():
        return f"Error: File not found: {filepath}"
    if not target.is_file():
        return f"Error: Not a file: {filepath}"

    try:
        with target.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError as exc:
        return f"Error: Could not read {filepath}: {exc}"

    start_index = start_line - 1
    end_index = min(end_line, len(lines))
    if start_index >= len(lines):
        return "Error: Start line is beyond end of file."

    return "".join(f"{line_number}: {lines[line_number - 1]}" for line_number in range(start_line, end_index + 1))


class GuardedPythonREPLTool(PythonREPLTool):
    def _run(self, query: str, run_manager: Any = None) -> str:
        output = super()._run(query, run_manager=run_manager)
        if output is None:
            output = ""
        if len(output) > REPL_OUTPUT_LIMIT:
            return REPL_GUARDRAIL_MESSAGE
        return output

    async def _arun(self, query: str, run_manager: Any = None) -> str:
        return await asyncio.to_thread(self._run, query, run_manager)


def build_system_prompt() -> str:
    return dedent(
        """
        You are a senior frontend replication agent working from one video and static local assets.

        You must work in exactly these three steps and in this order:

        Step 1 (Hypothesis)
        - Watch the provided video first.
        - Write a brief hypothesis of the interaction mechanics.
        - Keep it short and concrete.

        Step 2 (Data Extraction)
        - You MUST use the Python REPL tool to inspect files inside ./stripe_assets/.
        - You are strictly forbidden from printing the entirety of nav_before.html or nav_after.html. The DOM is too large.
        - You MUST use the pre-loaded grep(filepath, pattern) function to find specific elements, or read_slice(filepath, start, end) to view only surrounding context.
        - Example: grep('stripe_assets/nav_before.html', 'Products')
        - Do not guess colors, spacing, typography, icon paths, or DOM structure.
        - You MUST extract exact typography, colors, padding, and SVG path data from the available files.
        - You can parse the JSON style files natively.
        - Keep your queries surgical.
        - If an expected file is missing, inspect the files that are present and say which files you used instead.
        - Quote exact values only when you obtained them from tool output.

        Step 3 (Generation)
        - After you have the exact data, generate one complete React component in JSX using Tailwind CSS.
        - Replicate the layout, visual styling, and interaction mechanics from the video as accurately as possible.
        - Return a single self-contained component.
        - Do not split the code across multiple files.

        Final response format:
        - A heading for Step 1 with the hypothesis.
        - A heading for Step 2 with the extracted values and file evidence.
        - A heading for Step 3 with a short note followed by exactly one fenced ```jsx code block.

        Additional rules:
        - Never hallucinate SVG path values.
        - Never invent hex colors.
        - Prefer values from styles JSON when available.
        - Use the Python REPL tool before producing Step 2.
        - If a REPL output is too large, narrow the query immediately with grep() or read_slice().
        """
    ).strip()


async def upload_video_and_wait_active() -> Any:
    uploaded = await asyncio.to_thread(genai.upload_file, str(VIDEO_PATH), mime_type="video/mp4")

    while not getattr(uploaded, "state", None) or uploaded.state.name != "ACTIVE":
        state_name = getattr(getattr(uploaded, "state", None), "name", None)
        if state_name == "FAILED":
            raise RuntimeError(f"Gemini video processing failed for {uploaded.name}.")
        await asyncio.sleep(VIDEO_POLL_INTERVAL_SECONDS)
        uploaded = await asyncio.to_thread(genai.get_file, uploaded.name)

    return uploaded


async def delete_uploaded_file(uploaded: Any) -> None:
    if not uploaded:
        return
    try:
        await asyncio.to_thread(genai.delete_file, uploaded.name)
    except Exception:
        pass


def build_repl_tool() -> GuardedPythonREPLTool:
    repl_namespace = {
        "ASSETS_DIR": ASSETS_DIR,
        "PROJECT_ROOT": PROJECT_ROOT,
        "Path": Path,
        "json": json,
        "re": re,
        "grep": grep,
        "read_slice": read_slice,
    }
    tool = GuardedPythonREPLTool(globals=repl_namespace, locals=dict(repl_namespace))
    tool.name = "python_repl"
    tool.description = (
        "Execute Python to inspect files in ./stripe_assets/. "
        "Preloaded helpers: grep(filepath, pattern) and read_slice(filepath, start_line, end_line). "
        "Use this to load JSON, parse HTML surgically, extract SVG paths, colors, padding, font data, and other exact values."
    )
    return tool


def build_agent_executor(api_key: str) -> Any:
    tools = [build_repl_tool()]
    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=0,
        google_api_key=api_key,
    )
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=build_system_prompt(),
        debug=True,
        name="stripe_generate_agent",
    )


def build_input_messages(uploaded: Any) -> list[HumanMessage]:
    inventory = asset_inventory_text()
    instruction = dedent(
        f"""
        Analyze the Stripe mega-menu interaction using the uploaded video and the local files in ./stripe_assets/.

        Uploaded Gemini video URI: {uploaded.uri}
        Local asset inventory:
        {inventory}

        Important:
        - The uploaded video is the authoritative source for motion and interaction timing.
        - The local files are the authoritative source for exact DOM, styles, spacing, typography, and SVG paths.
        - Use the Python REPL tool to inspect the local files before generating the final component.
        """
    ).strip()

    return [
        HumanMessage(
            content=[
                {"type": "text", "text": instruction},
                {
                    "type": "media",
                    "file_uri": uploaded.uri,
                    "mime_type": "video/mp4",
                },
            ]
        )
    ]


def extract_agent_output_text(result: dict[str, Any]) -> str:
    messages = result.get("messages")
    if not isinstance(messages, list):
        raise RuntimeError("Agent result did not contain a messages list.")

    for message in reversed(messages):
        if isinstance(message, AIMessage):
            content = message.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_parts: list[str] = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(str(part.get("text", "")))
                    elif isinstance(part, str):
                        text_parts.append(part)
                joined = "\n".join(part for part in text_parts if part)
                if joined:
                    return joined
        elif isinstance(message, BaseMessage) and isinstance(message.content, str) and message.type == "ai":
            return message.content

    raise RuntimeError("Could not find the final AI message in the agent result.")


def extract_jsx_code(markdown: str) -> str:
    matches = re.findall(r"```(?:jsx|javascript|tsx|react)?\n(.*?)```", markdown, flags=re.DOTALL | re.IGNORECASE)
    if not matches:
        raise RuntimeError("Agent response did not contain a fenced code block.")
    return matches[-1].strip() + "\n"


async def run_agent() -> str:
    api_key = get_api_key()
    ensure_assets()
    ensure_output_dir()
    genai.configure(api_key=api_key)

    uploaded = None
    try:
        uploaded = await upload_video_and_wait_active()
        agent_executor = build_agent_executor(api_key)
        result = await agent_executor.ainvoke({"messages": build_input_messages(uploaded)})

        output = extract_agent_output_text(result)
        FINAL_RESPONSE_OUTPUT.write_text(output, encoding="utf-8")

        jsx = extract_jsx_code(output)
        OUTPUT_COMPONENT.write_text(jsx, encoding="utf-8")
        return output
    finally:
        await delete_uploaded_file(uploaded)


async def main() -> None:
    output = await run_agent()
    print(f"Saved final response to {FINAL_RESPONSE_OUTPUT.relative_to(PROJECT_ROOT)}")
    print(f"Saved component to {OUTPUT_COMPONENT.relative_to(PROJECT_ROOT)}")
    print()
    print(output)


if __name__ == "__main__":
    asyncio.run(main())
