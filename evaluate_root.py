from __future__ import annotations

import argparse
import asyncio
import base64
import difflib
import json
import os
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parent
STRIPE_ASSETS_DIR = PROJECT_ROOT / "stripe_assets"
EVAL_ASSETS_DIR = PROJECT_ROOT / "eval_assets"
FEEDBACK_OUTPUT = PROJECT_ROOT / "feedback_loop.txt"
MODEL_NAME = "gemini-3-flash-preview"
HTML_DIFF_LIMIT = 3_000
DEFAULT_TARGET_SELECTOR = "header, nav"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate generated UI assets against reference assets.")
    parser.add_argument(
        "--target-selector",
        default=DEFAULT_TARGET_SELECTOR,
        help=f"CSS selector used to isolate the DOM scope before diffing. Default: {DEFAULT_TARGET_SELECTOR!r}",
    )
    return parser.parse_args()


def get_api_key() -> str:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing API key. Set GOOGLE_API_KEY or GEMINI_API_KEY.")
    return api_key


def resolve_asset_path(candidates: list[Path], label: str) -> Path:
    for path in candidates:
        if path.exists():
            return path
    candidate_text = ", ".join(str(path.relative_to(PROJECT_ROOT)) for path in candidates)
    raise FileNotFoundError(f"Missing {label}. Checked: {candidate_text}")


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_target_html(html_string: str, selector: str) -> str:
    soup = BeautifulSoup(html_string, "html.parser")
    target = soup.select_one(selector)
    if target is None:
        warning = f"WARNING: selector {selector!r} not found. Falling back to full HTML.\n"
        return warning + soup.prettify()
    return target.prettify()


def build_html_diff_summary(original_html: str, generated_html: str, target_selector: str) -> str:
    original_scope = extract_target_html(original_html, target_selector)
    generated_scope = extract_target_html(generated_html, target_selector)

    diff_lines = difflib.unified_diff(
        original_scope.splitlines(),
        generated_scope.splitlines(),
        fromfile=f"stripe_assets[{target_selector}]",
        tofile=f"eval_assets[{target_selector}]",
        lineterm="",
    )
    diff_text = "\n".join(diff_lines)
    if not diff_text:
        return f"No structural HTML differences detected by unified_diff for selector {target_selector!r}."
    if len(diff_text) > HTML_DIFF_LIMIT:
        return diff_text[:HTML_DIFF_LIMIT] + "\n...[truncated]"
    return diff_text


def image_block(image_path: Path) -> dict[str, Any]:
    suffix = image_path.suffix.lower()
    if suffix == ".png":
        mime_type = "image/png"
    elif suffix in {".jpg", ".jpeg"}:
        mime_type = "image/jpeg"
    else:
        raise ValueError(f"Unsupported image type for {image_path}")

    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{mime_type};base64,{encoded}",
        },
    }


def build_human_message(html_diff_summary: str, image_paths: list[Path], target_selector: str) -> HumanMessage:
    prompt = (
        "You are evaluating the generated UI against the original, focusing STRICTLY on the element matching "
        f"the selector: {target_selector}.\n\n"
        "Review this HTML text diff showing structural differences for this specific component:\n\n"
        f"{html_diff_summary}\n\n"
        "Next, review the following three pairs of UI state screenshots: "
        "[1. Original Pre-Hover, 2. Generated Pre-Hover], "
        "[3. Original Hover, 4. Generated Hover], "
        "[5. Original Post-Hover, 6. Generated Post-Hover]. "
        "Pay attention to every minute difference that is present in each image pairs"
        "Synthesize the scoped HTML diff and the visual discrepancies into highly actionable feedback for a React/Tailwind developer. "
        "Be specific about CSS classes, padding, z-indexes, and DOM hierarchy. "
        'Output your evaluation as strict JSON: {"status": "PASS" | "FAIL", "refinement_pointers": ["pointer 1"]}.'
    )

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    content.extend(image_block(path) for path in image_paths)
    return HumanMessage(content=content)


def extract_text_from_response(response: Any) -> str:
    content = getattr(response, "content", None)
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
    raise RuntimeError("LLM response did not contain text content.")


def parse_evaluation_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError("Could not parse strict JSON from model response.") from None
        return json.loads(text[start : end + 1])


def write_feedback_if_needed(result: dict[str, Any]) -> None:
    status = result.get("status")
    pointers = result.get("refinement_pointers", [])

    if status == "FAIL":
        if not isinstance(pointers, list):
            raise RuntimeError("Expected refinement_pointers to be a list.")
        FEEDBACK_OUTPUT.write_text("\n".join(str(item) for item in pointers), encoding="utf-8")


async def evaluate(target_selector: str = DEFAULT_TARGET_SELECTOR) -> dict[str, Any]:
    api_key = get_api_key()

    original_nav_path = resolve_asset_path(
        [
            STRIPE_ASSETS_DIR / "nav.html",
            STRIPE_ASSETS_DIR / "hover" / "nav.html",
        ],
        "original nav HTML",
    )
    generated_nav_path = resolve_asset_path(
        [
            EVAL_ASSETS_DIR / "nav.html",
            EVAL_ASSETS_DIR / "hover" / "nav.html",
        ],
        "generated nav HTML",
    )

    image_paths = [
        resolve_asset_path([STRIPE_ASSETS_DIR / "pre_hover" / "pre_hover.png"], "original pre-hover image"),
        resolve_asset_path([EVAL_ASSETS_DIR / "pre_hover" / "pre_hover.png"], "generated pre-hover image"),
        resolve_asset_path([STRIPE_ASSETS_DIR / "hover" / "hover.png"], "original hover image"),
        resolve_asset_path([EVAL_ASSETS_DIR / "hover" / "hover.png"], "generated hover image"),
        resolve_asset_path([STRIPE_ASSETS_DIR / "post_hover" / "post_hover.png"], "original post-hover image"),
        resolve_asset_path([EVAL_ASSETS_DIR / "post_hover" / "post_hover.png"], "generated post-hover image"),
    ]

    original_html = read_text_file(original_nav_path)
    generated_html = read_text_file(generated_nav_path)
    html_diff_summary = build_html_diff_summary(original_html, generated_html, target_selector)

    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=0,
        google_api_key=api_key,
        response_mime_type="application/json",
    )
    message = build_human_message(html_diff_summary, image_paths, target_selector)
    response = await llm.ainvoke([message])
    parsed = parse_evaluation_json(extract_text_from_response(response))
    write_feedback_if_needed(parsed)
    return parsed


async def main() -> None:
    args = parse_args()

    try:
        result = await evaluate(target_selector=args.target_selector)
    except FileNotFoundError as exc:
        raise SystemExit(f"Asset error: {exc}") from exc

    print(json.dumps(result, indent=2))
    if result.get("status") == "FAIL":
        print(f"\nWrote refinement pointers to {FEEDBACK_OUTPUT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
