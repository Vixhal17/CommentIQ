import os
import time
import random
import yaml
from pathlib import Path
from typing import Any, Optional, Type, TypeVar, Union
from pydantic import BaseModel
import httpx
from sqlalchemy.orm import Session

from backend.config.settings import settings
from backend.app.core.logging import logger
from backend.app.llm.cache import ResponseCache, compute_cache_key
from backend.app.llm.budget import TokenBudgetGuard, BudgetExceededException
from backend.app.llm.parsers import strip_reasoning_tags, parse_and_validate_json
from backend.app.llm.mock_provider import MockProvider, MockHTTPStatusError

T = TypeVar("T", bound=BaseModel)


class LLMResult(BaseModel):
    content: str
    parsed: Optional[Any] = None
    model_used: str
    provider_used: str
    fallback_used: bool = False
    tokens_used: int = 0
    cached: bool = False
    judge_independent: bool = True
    error: Optional[str] = None


class LLMClient:
    """
    Robust, cost-aware LLM client implementing the $0 budget free-tier strategy.
    Supports Groq, Mistral, Ollama, and deterministic Mock testing.
    """

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        db: Optional[Session] = None,
        mock_provider: Optional[MockProvider] = None,
    ):
        self.config_path = Path(config_path or settings.LLM_CONFIG_PATH)
        self.config = self._load_config()
        self.db = db
        self.cache = ResponseCache(db=db)
        self.budget_guard = TokenBudgetGuard(
            daily_limit=self.config.get("budget", {}).get("daily_token_limit", 100000)
        )
        self.mock_provider = mock_provider

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"LLM configuration not found at {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _get_provider_details(self, provider_name: str) -> dict[str, Any]:
        providers = self.config.get("providers", {})
        if provider_name not in providers:
            raise ValueError(f"Unknown provider: '{provider_name}'. Defined: {list(providers.keys())}")
        info = providers[provider_name].copy()

        # Resolve API key from environment
        env_var = info.get("api_key_env")
        if env_var:
            info["api_key"] = os.environ.get(env_var, getattr(settings, env_var, ""))
        else:
            info["api_key"] = "ollama-dummy-key"
        return info

    def _send_openai_compatible_request(
        self,
        provider_name: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Dispatch HTTP request to OpenAI-compatible chat completion endpoint."""
        # Check mock provider first (for unit tests)
        if self.mock_provider is not None:
            return self.mock_provider.complete(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        provider_info = self._get_provider_details(provider_name)
        base_url = provider_info.get("base_url", "").rstrip("/")
        endpoint = f"{base_url}/chat/completions"
        api_key = provider_info.get("api_key", "")

        # Fail fast if provider requires key but has placeholder or empty key
        if provider_name != "ollama" and (not api_key or "your_" in api_key.lower()):
            raise ValueError(f"Provider '{provider_name}' has missing or unconfigured API key.")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            if response.status_code in (429, 500, 502, 503, 504):
                retry_after = response.headers.get("Retry-After", "")
                raise MockHTTPStatusError(
                    status_code=response.status_code,
                    message=response.text,
                    headers={"Retry-After": retry_after},
                )
            response.raise_for_status()
            return response.json()

    def _execute_with_retries(
        self,
        provider_name: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        retry_cfg = self.config.get("retry", {})
        max_retries = retry_cfg.get("max_retries", 3)
        base_backoff = retry_cfg.get("backoff_base_seconds", 1.0)
        max_backoff = retry_cfg.get("max_backoff_seconds", 15.0)
        use_jitter = retry_cfg.get("jitter", True)

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return self._send_openai_compatible_request(
                    provider_name=provider_name,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except (MockHTTPStatusError, httpx.HTTPStatusError) as http_err:
                if hasattr(http_err, "status_code"):
                    status_code = http_err.status_code
                elif hasattr(http_err, "response") and http_err.response is not None:
                    status_code = http_err.response.status_code
                else:
                    status_code = 500
                last_error = http_err
                if status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                    # Check Retry-After header
                    headers = getattr(http_err, "headers", {})
                    retry_after_str = headers.get("Retry-After") if headers else None
                    if retry_after_str and retry_after_str.isdigit():
                        sleep_seconds = float(retry_after_str)
                    else:
                        sleep_seconds = min(max_backoff, base_backoff * (2 ** attempt))
                        if use_jitter:
                            sleep_seconds += random.uniform(0.1, 0.5)

                    logger.warning(
                        f"Rate limit / server error ({status_code}) on {provider_name}:{model}. "
                        f"Retrying in {sleep_seconds:.2f}s (attempt {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(sleep_seconds)
                    continue
                else:
                    raise http_err
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    sleep_seconds = min(max_backoff, base_backoff * (2 ** attempt))
                    time.sleep(sleep_seconds)
                    continue
                raise last_error

        raise last_error or RuntimeError("Unknown error during LLM invocation")

    def call_role(
        self,
        role: str,
        messages: list[dict[str, str]],
        schema: Optional[Type[T]] = None,
        estimated_tokens: int = 500,
    ) -> LLMResult:
        """
        Execute an LLM call for a designated role ('classifier', 'drafter', 'judge').
        Implements caching, budget validation, retries, and fallback chains.
        """
        roles_cfg = self.config.get("roles", {})
        if role not in roles_cfg:
            raise ValueError(f"Role '{role}' not defined in LLM configuration. Available: {list(roles_cfg.keys())}")

        role_info = roles_cfg[role]
        primary_node = role_info.get("primary", {})
        fallback_nodes = role_info.get("fallbacks", [])

        chain = [(primary_node, False)] + [(node, True) for node in fallback_nodes]

        last_exception = None

        for target_node, is_fallback in chain:
            provider = target_node.get("provider")
            model = target_node.get("model")
            temp = target_node.get("temperature", 0.0)
            max_t = target_node.get("max_tokens", 500)

            call_params = {"temperature": temp, "max_tokens": max_t}
            cache_key = compute_cache_key(messages, model, call_params)

            # 1. Check cache first (costs zero tokens, zero calls)
            if self.config.get("budget", {}).get("cache_enabled", True):
                cached = self.cache.get(cache_key)
                if cached:
                    cached_data, cached_tokens = cached
                    raw_content = cached_data.get("content", "")
                    parsed_obj = None
                    if schema:
                        parsed_obj, _ = parse_and_validate_json(raw_content, schema)

                    judge_indep = True
                    if role == "drafter" and "mistral" in model.lower() and is_fallback:
                        judge_indep = False

                    return LLMResult(
                        content=raw_content,
                        parsed=parsed_obj,
                        model_used=model,
                        provider_used=provider,
                        fallback_used=is_fallback,
                        tokens_used=0,
                        cached=True,
                        judge_independent=judge_indep,
                    )

            # 2. Check token budget guard
            try:
                self.budget_guard.check_budget_available(estimated_tokens)
            except BudgetExceededException as be:
                return LLMResult(
                    content="",
                    model_used=model,
                    provider_used=provider,
                    fallback_used=is_fallback,
                    error=str(be),
                )

            # 3. Call LLM with retries
            try:
                raw_response = self._execute_with_retries(
                    provider_name=provider,
                    model=model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=max_t,
                )

                content = raw_response["choices"][0]["message"]["content"]
                cleaned_content = strip_reasoning_tags(content)
                usage = raw_response.get("usage", {})
                tokens_used = usage.get("total_tokens", estimated_tokens)

                # Record token consumption
                self.budget_guard.record_usage(tokens_used)

                # Validate schema if provided
                parsed_obj = None
                if schema:
                    parsed_obj, err = parse_and_validate_json(cleaned_content, schema)
                    if err:
                        # Retry once with a corrective message
                        logger.warning(f"Schema validation failed: {err}. Retrying once...")
                        fix_messages = list(messages) + [
                            {"role": "assistant", "content": cleaned_content},
                            {"role": "user", "content": f"Your response was invalid JSON. Error: {err}. Provide ONLY valid JSON matching the schema."},
                        ]
                        fix_resp = self._execute_with_retries(
                            provider_name=provider,
                            model=model,
                            messages=fix_messages,
                            temperature=0.0,
                            max_tokens=max_t,
                        )
                        fix_content = strip_reasoning_tags(fix_resp["choices"][0]["message"]["content"])
                        parsed_obj, _ = parse_and_validate_json(fix_content, schema)
                        if parsed_obj is not None:
                            cleaned_content = fix_content

                # Cache successful response
                if self.config.get("budget", {}).get("cache_enabled", True):
                    self.cache.set(cache_key, {"content": cleaned_content}, tokens=tokens_used)

                # Check independence rule:
                # If drafter fell back to Mistral, mark judge independence as False!
                judge_indep = True
                if role == "drafter" and "mistral" in model.lower() and is_fallback:
                    judge_indep = False
                    logger.warning("Drafter used Mistral fallback: flagging 'judge not independent' for verifier!")

                return LLMResult(
                    content=cleaned_content,
                    parsed=parsed_obj,
                    model_used=model,
                    provider_used=provider,
                    fallback_used=is_fallback,
                    tokens_used=tokens_used,
                    cached=False,
                    judge_independent=judge_indep,
                )

            except Exception as e:
                logger.warning(f"Provider {provider}:{model} failed: {e}. Moving to next fallback in chain...")
                last_exception = e
                continue

        # If all nodes in the chain failed
        return LLMResult(
            content="",
            model_used="",
            provider_used="",
            fallback_used=True,
            error=f"All models in fallback chain for role '{role}' failed. Last error: {last_exception}",
        )

