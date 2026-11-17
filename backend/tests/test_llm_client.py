import pytest
from pydantic import BaseModel
from backend.app.llm.client import LLMClient
from backend.app.llm.budget import BudgetExceededException
from backend.app.llm.parsers import strip_reasoning_tags, parse_and_validate_json


class ClassificationSchema(BaseModel):
    category: str
    confidence: float
    rationale: str
    sensitive: bool


def test_llm_cache_prevents_duplicate_calls(llm_client, mock_llm):
    messages = [{"role": "user", "content": "Classify this comment: 'Great job!'"}]

    # Call 1: Misses cache, calls provider
    res1 = llm_client.call_role("classifier", messages, schema=ClassificationSchema)
    assert not res1.cached
    assert len(mock_llm.call_history) == 1
    assert res1.parsed is not None
    assert res1.parsed.category == "question"

    # Call 2: Identical prompt, must hit cache and invoke 0 calls
    res2 = llm_client.call_role("classifier", messages, schema=ClassificationSchema)
    assert res2.cached
    assert res2.tokens_used == 0
    assert len(mock_llm.call_history) == 1  # No new call made!
    assert res2.content == res1.content


def test_retry_on_429_rate_limit(llm_client, mock_llm):
    messages = [{"role": "user", "content": "How do I run this?"}]

    # Queue a 429 error followed by a success
    mock_llm.queue_error(429, message="Rate limit exceeded", retry_after="0")
    mock_llm.queue_response('{"category": "question", "confidence": 0.99, "rationale": "Asks how to run", "sensitive": false}')

    res = llm_client.call_role("classifier", messages, schema=ClassificationSchema)
    assert res.error is None
    assert res.parsed.category == "question"
    assert len(mock_llm.call_history) == 2  # 1 failed + 1 retried


def test_fallback_chain_and_independence_flag(llm_client, mock_llm):
    messages = [{"role": "user", "content": "Draft an answer to this question"}]

    # Simulate primary model permanently failing with 500 error
    for _ in range(4):  # max_retries + 1
        mock_llm.queue_error(500, message="Internal Server Error")

    # Queue successful response on fallback
    mock_llm.queue_response("Here is the drafted response based on the transcript.", model="mistral-large-4")

    # Call drafter role
    res = llm_client.call_role("drafter", messages)
    assert res.fallback_used
    assert "mistral" in res.model_used.lower()

    # Rule: If drafter used Mistral fallback, judge independence must be False!
    assert res.judge_independent is False


def test_token_budget_guard(llm_client, mock_llm):
    # Set daily limit to 100 tokens
    llm_client.budget_guard.daily_limit = 100
    llm_client.budget_guard._tokens_used_today = 90

    # Requesting 500 estimated tokens exceeds the 100 limit
    messages = [{"role": "user", "content": "Exceed budget"}]
    res = llm_client.call_role("classifier", messages, estimated_tokens=500)
    assert res.error is not None
    assert "Daily token budget exceeded" in res.error
    assert len(mock_llm.call_history) == 0  # Guard intercepted before network call


def test_strip_reasoning_tags():
    raw_with_tags = "<think>Analyzing comment tone... User seems happy.</think>{\"category\": \"praise\", \"confidence\": 0.9, \"rationale\": \"Praise\", \"sensitive\": false}"
    cleaned = strip_reasoning_tags(raw_with_tags)
    assert "<think>" not in cleaned
    assert "</think>" not in cleaned

    parsed, err = parse_and_validate_json(cleaned, ClassificationSchema)
    assert err is None
    assert parsed.category == "praise"

