"""
Shared utilities: Anthropic API client, LLM call wrapper, and JSON extraction.
"""

import json
import os
import re
import time
import anthropic


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "No API key found. Set ANTHROPIC_API_KEY environment variable."
        )
    return anthropic.Anthropic(api_key=api_key)


def llm_call(
    client: anthropic.Anthropic,
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-haiku-4-5-20251001",
    temperature: float = 0.3,
    retries: int = 3,
) -> str:
    """
    Call the Anthropic API with retry logic on transient failures.
    Returns the raw text content of the model's response.
    """
    for attempt in range(1, retries + 1):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=4096,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return message.content[0].text
        except Exception as e:
            if attempt == retries:
                raise
            wait = 2 ** attempt
            print(f"  [LLM retry {attempt}/{retries}] Error: {e}. Waiting {wait}s...")
            time.sleep(wait)


def extract_json(text: str) -> dict | list:
    """
    Robustly extract a JSON object or array from LLM output.
    Handles: clean JSON, markdown code blocks, leading/trailing prose.
    """
    if not text:
        return {}

    # Strip markdown fences (```json ... ``` or ``` ... ```)
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if fenced:
        candidate = fenced.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Try the raw text directly
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Find the first { or [ and try from there
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue

    # Last resort: return the text in a wrapper dict
    return {"raw_response": text}


def log_step(step_num: int, title: str) -> None:
    print(f"\n{'─' * 55}")
    print(f"  Step {step_num}: {title}")
    print(f"{'─' * 55}")
