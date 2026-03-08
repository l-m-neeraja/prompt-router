"""
LLM-Powered Prompt Router for Intent Classification.

This service classifies user intent and routes requests to specialized AI personas.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

from prompts import (
    CLASSIFIER_PROMPT,
    CLARIFICATION_PROMPT,
    EXPERT_PROMPTS,
)

load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "gpt-4o-mini")
GENERATION_MODEL = os.getenv("GENERATION_MODEL", "gpt-4o")
ROUTE_LOG_PATH = Path(os.getenv("ROUTE_LOG_PATH", "route_log.jsonl"))

# Optional: confidence threshold (stretch goal - if confidence < threshold, treat as unclear)
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.0"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_client() -> OpenAI:
    """Get OpenAI client, raising if API key is missing."""
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required. "
            "Set it in .env or export it before running."
        )
    return OpenAI(api_key=OPENAI_API_KEY)


def classify_intent(message: str) -> dict:
    """
    Classify user intent using an LLM call.

    Returns a dict with keys: intent (str), confidence (float).
    On malformed JSON or parse errors, defaults to {"intent": "unclear", "confidence": 0.0}.
    """
    client = _get_client()
    prompt = CLASSIFIER_PROMPT.format(message=message)

    try:
        response = client.chat.completions.create(
            model=CLASSIFIER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=50,
        )
        content = response.choices[0].message.content or ""
    except Exception as e:
        logger.error("LLM API call failed for classification: %s", e)
        return {"intent": "unclear", "confidence": 0.0}

    # Parse JSON - handle malformed responses
    content = content.strip()
    # Remove markdown code blocks if present
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        parsed = json.loads(content)
        intent = parsed.get("intent", "unclear")
        confidence = float(parsed.get("confidence", 0.0))

        # Validate intent is one of the allowed values
        valid_intents = {"code", "data", "writing", "career", "unclear"}
        if intent not in valid_intents:
            intent = "unclear"
            confidence = 0.0

        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(1.0, confidence))

        return {"intent": intent, "confidence": confidence}
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning("Failed to parse classifier response: %s. Raw: %s", e, content)
        return {"intent": "unclear", "confidence": 0.0}


def route_and_respond(message: str, intent: dict) -> str:
    """
    Route the message to the appropriate expert persona and generate a response.

    If intent is 'unclear', generates a clarifying question instead of routing.
    """
    intent_label = intent.get("intent", "unclear")
    confidence = intent.get("confidence", 0.0)

    # Apply confidence threshold if configured
    if CONFIDENCE_THRESHOLD > 0 and confidence < CONFIDENCE_THRESHOLD:
        intent_label = "unclear"

    client = _get_client()

    if intent_label == "unclear":
        # Generate clarifying question
        response = client.chat.completions.create(
            model=GENERATION_MODEL,
            messages=[
                {"role": "system", "content": CLARIFICATION_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0.5,
            max_tokens=150,
        )
        return (response.choices[0].message.content or "").strip()

    # Look up expert prompt
    system_prompt = EXPERT_PROMPTS.get(intent_label)
    if not system_prompt:
        # Fallback to clarification if intent not in our map
        response = client.chat.completions.create(
            model=GENERATION_MODEL,
            messages=[
                {"role": "system", "content": CLARIFICATION_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0.5,
            max_tokens=150,
        )
        return (response.choices[0].message.content or "").strip()

    # Generate response with expert persona
    response = client.chat.completions.create(
        model=GENERATION_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        temperature=0.6,
        max_tokens=1024,
    )
    return (response.choices[0].message.content or "").strip()


def log_route(intent: str, confidence: float, user_message: str, final_response: str) -> None:
    """Append a routing decision and response to the JSON Lines log file."""
    entry = {
        "intent": intent,
        "confidence": confidence,
        "user_message": user_message,
        "final_response": final_response,
    }
    with open(ROUTE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info("Logged route: intent=%s confidence=%.2f", intent, confidence)


def _parse_manual_override(message: str) -> Tuple[Optional[str], str]:
    """
    Check for manual intent override via @intent prefix.
    Returns (intent_label, stripped_message) or (None, message) if no override.
    """
    stripped = message.strip()
    valid_prefixes = ("@code", "@data", "@writing", "@career", "@unclear")
    for prefix in valid_prefixes:
        if stripped.lower().startswith(prefix):
            rest = stripped[len(prefix) :].strip()
            return prefix[1:].lower(), rest or message
    return None, message


def process_message(message: str) -> str:
    """
    Full pipeline: classify intent, route and respond, log the result.
    Supports manual override via @intent prefix (e.g., @code Fix this bug).
    """
    override_intent, effective_message = _parse_manual_override(message)
    if override_intent is not None:
        intent_result = {"intent": override_intent, "confidence": 1.0}
        message_for_llm = effective_message
    else:
        intent_result = classify_intent(message)
        message_for_llm = message

    final_response = route_and_respond(message_for_llm, intent_result)
    final_response = route_and_respond(message, intent_result)
    log_route(
        intent=intent_result["intent"],
        confidence=intent_result["confidence"],
        user_message=message,
        final_response=final_response,
    )
    return final_response


def main():
    """Simple CLI for interactive testing."""
    print("LLM Prompt Router - Type a message and press Enter. Type 'quit' to exit.\n")
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                break
            response = process_message(user_input)
            print(f"\nAssistant: {response}\n")
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.exception("Error processing message")
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
