import re
import json
from typing import Type, TypeVar, Optional, Tuple, Any
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

# Regex to strip thinking/reasoning traces such as <think>...</think>
THINK_TAG_REGEX = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)

def strip_reasoning_tags(text: str) -> str:
    """
    Strips reasoning/chain-of-thought blocks enclosed in <think>...</think>
    from reasoning models before parsing the final output.
    """
    if not text:
        return ""
    cleaned = THINK_TAG_REGEX.sub("", text).strip()
    return cleaned

def extract_json_str(text: str) -> str:
    """
    Extracts raw JSON string from potentially markdown-fenced text
    (e.g., ```json { ... } ``` or raw {...}).
    """
    cleaned = strip_reasoning_tags(text).strip()
    
    # Check for markdown code fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        return fence_match.group(1).strip()
        
    # Check for outermost JSON object or array brackets
    start_brace = cleaned.find("{")
    end_brace = cleaned.rfind("}")
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        return cleaned[start_brace:end_brace + 1].strip()

    start_bracket = cleaned.find("[")
    end_bracket = cleaned.rfind("]")
    if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
        return cleaned[start_bracket:end_bracket + 1].strip()

    return cleaned

def parse_and_validate_json(
    raw_response: str,
    schema: Type[T]
) -> Tuple[Optional[T], Optional[str]]:
    """
    Strips reasoning traces, extracts JSON, and validates against a Pydantic schema.
    Returns (validated_model, error_message).
    """
    cleaned_json = extract_json_str(raw_response)
    try:
        data = json.loads(cleaned_json)
    except json.JSONDecodeError as jde:
        return None, f"JSON decode error: {jde}. Raw snippet: {cleaned_json[:150]}"

    try:
        instance = schema.model_validate(data)
        return instance, None
    except ValidationError as ve:
        return None, f"Schema validation error: {ve}"

