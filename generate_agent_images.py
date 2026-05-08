from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from pathlib import Path
from textwrap import dedent
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware.tool_call_limit import ToolCallLimitMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_experimental.tools import PythonREPLTool
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "stripe_assets"
PRE_HOVER_IMAGE = ASSETS_DIR / "pre_hover" / "pre_hover.png"
HOVER_IMAGE = ASSETS_DIR / "hover" / "hover.png"
POST_HOVER_IMAGE = ASSETS_DIR / "post_hover" / "post_hover.png"
EVAL_ASSETS_DIR = PROJECT_ROOT / "eval_assets"
EVAL_PRE_HOVER_IMAGE = EVAL_ASSETS_DIR / "pre_hover" / "pre_hover.png"
EVAL_HOVER_IMAGE = EVAL_ASSETS_DIR / "hover" / "hover.png"
EVAL_POST_HOVER_IMAGE = EVAL_ASSETS_DIR / "post_hover" / "post_hover.png"
FRONTEND_DIR = PROJECT_ROOT / "generated-page"
GENERATED_COMPONENT_DIR = FRONTEND_DIR / "src" / "generated"
OUTPUT_COMPONENT = GENERATED_COMPONENT_DIR / "GeneratedMegaMenuFromImages.jsx"
LEGACY_OUTPUT_COMPONENT = PROJECT_ROOT / "GeneratedMegaMenu.jsx"
FEEDBACK_FILE = PROJECT_ROOT / "feedback_loop.txt"
INTEGRATED_FEEDBACK_FILE = PROJECT_ROOT / "feedback_integrated.txt"
MODEL_NAME = "gemini-3-flash-preview"
FILE_POLL_INTERVAL_SECONDS = 5
FINAL_RESPONSE_OUTPUT = PROJECT_ROOT / "generate_agent_images_response.md"
DEFAULT_MAX_TOOL_CALLS = 50
GREP_OUTPUT_LIMIT = 2_000
REPL_OUTPUT_LIMIT = 10_000
REPL_GUARDRAIL_MESSAGE = (
    "Error: Output exceeded 10,000 characters. Context window protected. "
    "Please use grep(filepath, pattern) or read_slice(filepath, start, end) "
    "to extract only the specific lines you need."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate or refine the Stripe mega menu from screenshots.")
    parser.add_argument(
        "--max-tool-calls",
        type=int,
        default=DEFAULT_MAX_TOOL_CALLS,
        help=f"Hard limit for Python REPL tool calls within a single agent run. Default: {DEFAULT_MAX_TOOL_CALLS}",
    )
    return parser.parse_args()


def get_api_key() -> str:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing API key. Set GOOGLE_API_KEY or GEMINI_API_KEY before running generate_agent_images.py."
        )
    return api_key


def ensure_assets() -> None:
    if not ASSETS_DIR.exists():
        raise FileNotFoundError(f"Missing assets directory: {ASSETS_DIR}")
    for path in (PRE_HOVER_IMAGE, HOVER_IMAGE, POST_HOVER_IMAGE):
        if not path.exists():
            raise FileNotFoundError(f"Missing image file: {path}")


def ensure_refine_assets() -> None:
    for path in (EVAL_PRE_HOVER_IMAGE, EVAL_HOVER_IMAGE, EVAL_POST_HOVER_IMAGE):
        if not path.exists():
            raise FileNotFoundError(f"Missing refine/eval image file: {path}")


def asset_inventory_text() -> str:
    files = sorted(path.relative_to(PROJECT_ROOT).as_posix() for path in ASSETS_DIR.rglob("*") if path.is_file())
    if not files:
        raise RuntimeError("stripe_assets/ is empty.")
    return "\n".join(f"- {item}" for item in files)


def ensure_output_dir() -> None:
    GENERATED_COMPONENT_DIR.mkdir(parents=True, exist_ok=True)


def get_existing_component_path() -> Path | None:
    if OUTPUT_COMPONENT.exists():
        return OUTPUT_COMPONENT
    if LEGACY_OUTPUT_COMPONENT.exists():
        return LEGACY_OUTPUT_COMPONENT
    return None


def in_refine_mode() -> bool:
    return FEEDBACK_FILE.exists() and get_existing_component_path() is not None


def load_feedback_text() -> str:
    return FEEDBACK_FILE.read_text(encoding="utf-8").strip()


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


def build_initial_system_prompt(max_tool_calls: int) -> str:
    return dedent(
        f"""
        You are a senior frontend replication agent working from three screenshots and static local assets.

        You must work in exactly these three steps and in this order:

        Tool-use budget:
        - You have a hard limit of {max_tool_calls} Python REPL tool calls in this run.
        - If you are close to the limit, stop investigating and produce the best final JSX you can.
        - Even if the tool budget is exhausted, your final answer must still include exactly one complete JSX component.
        - Wrap that final component in a fenced ```jsx code block.

        Step 1 (Hypothesis)
        - Inspect the provided screenshots first.
        - Write a brief hypothesis of the interaction mechanics across pre-hover, hover, and post-hover.
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
        - Replicate the layout, visual styling, and interaction mechanics from the screenshots as accurately as possible.
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


def build_refine_system_prompt(feedback_text: str, component_path: Path, max_tool_calls: int) -> str:
    component_reference = component_path.relative_to(PROJECT_ROOT).as_posix()
    return (
        "You are a Senior React Developer fixing bugs in your previously generated component.\n\n"
        f"You have a hard limit of {max_tool_calls} Python REPL tool calls in this run. "
        "After that budget is exhausted, you must stop investigating and produce your final corrected JSX.\n"
        "Your final answer must still include exactly one complete component wrapped in a fenced ```jsx code block.\n\n"
        "You have been provided two image sets for this refine pass:\n"
        "- The original images are the ground-truth target states.\n"
        "- The generated images are the latest iteration of the development output.\n\n"
        "The QA Evaluation Agent has flagged the following issues:\n\n"
        f"{feedback_text}\n\n"
        "Treat that feedback as a focused clue list about issues that may be present in the latest generation, not as a complete substitute for investigation.\n\n"
        "You have full access to the Python REPL. Do NOT just guess the fixes. "
        "If the feedback says a color, layout, or SVG is wrong, use your REPL to grep the original assets in "
        "./stripe_assets/ to find the correct data. You can also use the REPL to read your existing "
        f"./{component_reference} file to see exactly where your code went wrong. "
        "Compare the original images against the generated images to understand what the latest iteration still gets wrong. "
        "Once you have investigated the ground truth, rewrite the complete, corrected .jsx file to fix the issues."
    )


async def upload_file_and_wait_active(path: Path, mime_type: str) -> Any:
    uploaded = await asyncio.to_thread(genai.upload_file, str(path), mime_type=mime_type)

    while not getattr(uploaded, "state", None) or uploaded.state.name != "ACTIVE":
        state_name = getattr(getattr(uploaded, "state", None), "name", None)
        if state_name == "FAILED":
            raise RuntimeError(f"Gemini file processing failed for {uploaded.name}.")
        await asyncio.sleep(FILE_POLL_INTERVAL_SECONDS)
        uploaded = await asyncio.to_thread(genai.get_file, uploaded.name)

    return uploaded


async def upload_images_and_wait_active() -> dict[str, Any]:
    return {
        "pre_hover": await upload_file_and_wait_active(PRE_HOVER_IMAGE, "image/png"),
        "hover": await upload_file_and_wait_active(HOVER_IMAGE, "image/png"),
        "post_hover": await upload_file_and_wait_active(POST_HOVER_IMAGE, "image/png"),
    }


async def upload_refine_images_and_wait_active() -> dict[str, Any]:
    return {
        "original_pre_hover": await upload_file_and_wait_active(PRE_HOVER_IMAGE, "image/png"),
        "generated_pre_hover": await upload_file_and_wait_active(EVAL_PRE_HOVER_IMAGE, "image/png"),
        "original_hover": await upload_file_and_wait_active(HOVER_IMAGE, "image/png"),
        "generated_hover": await upload_file_and_wait_active(EVAL_HOVER_IMAGE, "image/png"),
        "original_post_hover": await upload_file_and_wait_active(POST_HOVER_IMAGE, "image/png"),
        "generated_post_hover": await upload_file_and_wait_active(EVAL_POST_HOVER_IMAGE, "image/png"),
    }


async def delete_uploaded_files(uploaded_files: dict[str, Any]) -> None:
    for uploaded in uploaded_files.values():
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


def build_agent_executor(api_key: str, system_prompt: str, max_tool_calls: int) -> Any:
    tools = [build_repl_tool()]
    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=0,
        google_api_key=api_key,
    )
    middleware = [
        ToolCallLimitMiddleware(
            run_limit=max_tool_calls,
            exit_behavior="continue",
        )
    ]
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware,
        debug=True,
        name="stripe_generate_agent_images",
    )


def build_initial_input_messages(uploaded_files: dict[str, Any]) -> list[HumanMessage]:
    inventory = asset_inventory_text()
    instruction = dedent(
        f"""
        Analyze the Stripe mega-menu interaction using the provided screenshots and the local files in ./stripe_assets/.

        Uploaded Gemini image URIs:
        - pre-hover: {uploaded_files["pre_hover"].uri}
        - hover: {uploaded_files["hover"].uri}
        - post-hover: {uploaded_files["post_hover"].uri}

        Local asset inventory:
        {inventory}

        Important:
        - The uploaded screenshots are the authoritative source for visual state across pre-hover, hover, and post-hover.
        - The local files are the authoritative source for exact DOM, styles, spacing, typography, and SVG paths.
        - Use the Python REPL tool to inspect the local files before generating the final component.
        """
    ).strip()

    return [
        HumanMessage(
            content=[
                {"type": "text", "text": instruction},
                {"type": "media", "file_uri": uploaded_files["pre_hover"].uri, "mime_type": "image/png"},
                {"type": "media", "file_uri": uploaded_files["hover"].uri, "mime_type": "image/png"},
                {"type": "media", "file_uri": uploaded_files["post_hover"].uri, "mime_type": "image/png"},
            ]
        )
    ]


def build_refine_input_messages(uploaded_files: dict[str, Any], component_path: Path) -> list[HumanMessage]:
    inventory = asset_inventory_text()
    component_reference = component_path.relative_to(PROJECT_ROOT).as_posix()
    instruction = dedent(
        f"""
        Refine the existing generated component using the screenshots and the local assets.

        Existing component path:
        - {component_reference}

        Uploaded Gemini image URIs:
        - original pre-hover: {uploaded_files["original_pre_hover"].uri}
        - generated pre-hover: {uploaded_files["generated_pre_hover"].uri}
        - original hover: {uploaded_files["original_hover"].uri}
        - generated hover: {uploaded_files["generated_hover"].uri}
        - original post-hover: {uploaded_files["original_post_hover"].uri}
        - generated post-hover: {uploaded_files["generated_post_hover"].uri}

        Local asset inventory:
        {inventory}

        Important:
        - The original screenshots are the ground-truth target states.
        - The generated screenshots are the latest iteration of the development output.
        - The local files in ./stripe_assets/ are the source of truth for exact DOM, styles, spacing, typography, and SVG paths.
        - feedback_loop.txt may highlight issues that are prevalent in the latest generation, but you should verify them against the assets.
        - Use the Python REPL as a debugging tool before rewriting the component.
        """
    ).strip()

    return [
        HumanMessage(
            content=[
                {"type": "text", "text": instruction},
                {"type": "media", "file_uri": uploaded_files["original_pre_hover"].uri, "mime_type": "image/png"},
                {"type": "media", "file_uri": uploaded_files["generated_pre_hover"].uri, "mime_type": "image/png"},
                {"type": "media", "file_uri": uploaded_files["original_hover"].uri, "mime_type": "image/png"},
                {"type": "media", "file_uri": uploaded_files["generated_hover"].uri, "mime_type": "image/png"},
                {"type": "media", "file_uri": uploaded_files["original_post_hover"].uri, "mime_type": "image/png"},
                {"type": "media", "file_uri": uploaded_files["generated_post_hover"].uri, "mime_type": "image/png"},
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
    if matches:
        return matches[-1].strip() + "\n"

    stripped = markdown.strip()
    jsx_markers = (
        "import React",
        "export default",
        "function ",
        "const ",
        "return (",
        "return <",
    )
    if any(marker in stripped for marker in jsx_markers):
        return stripped + ("\n" if not stripped.endswith("\n") else "")

    raise RuntimeError("Agent response did not contain recognizable JSX output.")


async def run_agent(max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS) -> str:
    if max_tool_calls < 1:
        raise RuntimeError("max_tool_calls must be at least 1.")

    api_key = get_api_key()
    ensure_assets()
    ensure_output_dir()
    refine_mode = in_refine_mode()
    if refine_mode:
        ensure_refine_assets()
    genai.configure(api_key=api_key)

    uploaded_files: dict[str, Any] = {}
    try:
        uploaded_files = (
            await upload_refine_images_and_wait_active()
            if refine_mode
            else await upload_images_and_wait_active()
        )
        component_path = get_existing_component_path()

        if refine_mode:
            if component_path is None:
                raise RuntimeError("Refine mode was requested but no generated component file was found.")
            system_prompt = build_refine_system_prompt(load_feedback_text(), component_path, max_tool_calls)
            input_messages = build_refine_input_messages(uploaded_files, component_path)
        else:
            system_prompt = build_initial_system_prompt(max_tool_calls)
            input_messages = build_initial_input_messages(uploaded_files)

        agent_executor = build_agent_executor(api_key, system_prompt, max_tool_calls)
        result = await agent_executor.ainvoke({"messages": input_messages})

        output = extract_agent_output_text(result)
        FINAL_RESPONSE_OUTPUT.write_text(output, encoding="utf-8")

        jsx = extract_jsx_code(output)
        OUTPUT_COMPONENT.write_text(jsx, encoding="utf-8")
        if refine_mode and FEEDBACK_FILE.exists():
            if INTEGRATED_FEEDBACK_FILE.exists():
                INTEGRATED_FEEDBACK_FILE.unlink()
            FEEDBACK_FILE.rename(INTEGRATED_FEEDBACK_FILE)
        return output
    finally:
        await delete_uploaded_files(uploaded_files)


async def main() -> None:
    args = parse_args()
    output = await run_agent(max_tool_calls=args.max_tool_calls)
    print(f"Saved final response to {FINAL_RESPONSE_OUTPUT.relative_to(PROJECT_ROOT)}")
    print(f"Saved component to {OUTPUT_COMPONENT.relative_to(PROJECT_ROOT)}")
    print()
    print(output)


if __name__ == "__main__":
    asyncio.run(main())
