from typing import Any, Optional
import json

class MockHTTPStatusError(Exception):
    def __init__(self, status_code: int, message: str, headers: Optional[dict[str, str]] = None):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.headers = headers or {}


class MockProvider:
    """
    Deterministic in-memory mock provider for testing LLMClient.
    Enables zero-cost unit testing without any network calls or real API keys.
    """

    def __init__(self):
        self.call_history: list[dict[str, Any]] = []
        self._preset_responses: list[Any] = []
        self._simulate_rate_limit: int = 0
        self._simulate_error_status: Optional[int] = None

    def queue_response(self, content: str, total_tokens: int = 50, model: str = "mock-model") -> None:
        """Queue a successful mock response."""
        response_payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": total_tokens - 20,
                "total_tokens": total_tokens
            },
            "model": model
        }
        self._preset_responses.append(response_payload)

    def queue_error(self, status_code: int, message: str = "Rate limit exceeded", retry_after: str = "1") -> None:
        """Queue an HTTP error to simulate 429 rate limits or 5xx server issues."""
        self._preset_responses.append(
            MockHTTPStatusError(status_code, message, headers={"Retry-After": retry_after})
        )

    def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 500,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Simulate an OpenAI-compatible /chat/completions endpoint."""
        call_record = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "kwargs": kwargs,
        }
        self.call_history.append(call_record)

        if self._preset_responses:
            next_resp = self._preset_responses.pop(0)
            if isinstance(next_resp, Exception):
                raise next_resp
            return next_resp

        # Realistic heuristic fallback when no preset response is queued
        prompt_str = ""
        if messages:
            prompt_str = messages[-1].get("content", "").lower()

        # 1. Intent Classification Prompt
        if "comment to classify" in prompt_str or "categories:" in prompt_str:
            # Inspect the target comment text specifically (ignore category instructions)
            comment_text = prompt_str.split("comment to classify:")[-1] if "comment to classify:" in prompt_str else prompt_str

            # Detect if custom categories are listed
            custom_cat_names = []
            if "categories:" in prompt_str:
                cat_block = prompt_str.split("categories:")[-1].split("rules:")[0]
                import re
                custom_cat_names = re.findall(r'"([^"]+)"', cat_block)

            if any(k in comment_text for k in ["bitcoin", "giveaway", "whatsapp", "telegram", "t.me", "fastmoney", "hot single", "free link", "2 btc"]):
                cat, conf, sens, rat = "spam", 0.99, False, "Promotional spam or financial scam"
            elif any(k in comment_text for k in ["self-harm", "suicide", "cutting myself", "kill myself", "trigger warning"]):
                cat, conf, sens, rat = "sensitive", 0.99, True, "Content safety or mental health crisis trigger"
            elif any(k in comment_text for k in ["refund", "billing", "charge", "invoice", "money back", "cancel"]):
                cat, conf, sens, rat = "refund_billing", 0.96, False, "Billing or refund request"
            elif any(k in comment_text for k in ["feature", "add support", "can you add", "suggestion", "roadmap"]):
                cat, conf, sens, rat = "feature_request", 0.95, False, "Viewer feature request or proposal"
            elif any(k in comment_text for k in ["sponsor", "collaborate", "partnership", "podcast", "guest speaker", "partnerships@"]):
                cat, conf, sens, rat = "business_collab", 0.96, False, "Business sponsorship or partnership outreach"
            elif any(k in comment_text for k in ["dict.get", "04:12", "01:30", "create extension", "warning", "errata"]) and not any(k in comment_text for k in ["broken", "crashes"]):
                cat, conf, sens, rat = "technical_correction", 0.94, False, "Technical code correction or version warning"
            elif any(k in comment_text for k in ["completely broken", "crashes", "hurts my ears", "fix your scripts", "fix it", "out of sync", "bug", "error"]):
                cat, conf, sens, rat = "complaint", 0.95, False, "Viewer complaint regarding video or code issues"
            elif any(k in comment_text for k in ["amazing explanation", "awesome video", "thank you", "saved me hours", "great tutorial", "love your"]):
                cat, conf, sens, rat = "praise", 0.97, False, "Positive viewer feedback and appreciation"
            else:
                cat, conf, sens, rat = "question", 0.95, False, "Viewer technical question regarding video tutorial"

            # Reconcile with custom category names if defined
            if custom_cat_names:
                cat_lower = cat.lower()
                matched = next((c for c in custom_cat_names if c.lower() in cat_lower or cat_lower in c.lower()), None)
                if matched:
                    cat = matched
                else:
                    cat = custom_cat_names[0]

            default_content = json.dumps({
                "category": cat,
                "confidence": conf,
                "rationale": rat,
                "sensitive": sens,
            })

        # 2. Ask AI Assistant Prompt (Sample Response Generator)
        elif "ai creator assistant" in prompt_str or "detected category:" in prompt_str or "critical rules:" in prompt_str:
            is_sens = "category: sensitive" in prompt_str or "sensitive" in prompt_str and ("self-harm" in prompt_str or "legal" in prompt_str or "harassment" in prompt_str or "threat" in prompt_str)
            if is_sens:
                default_content = json.dumps({
                    "is_sensitive": True,
                    "sensitive_notice": "⚠️ SENSITIVE CASE NOTICE: This comment has been classified as a sensitive case (safety, legal dispute, harassment, or self-harm risk). Handle with caution and avoid public escalation.",
                    "guidance": "Explicit sensitive case handling: maintain calm, de-escalate without admitting liability, and direct to private support.",
                    "sample_response": "Thank you for reaching out. Please contact our dedicated support team directly at support@channel.com so we can address your concerns privately and safely.",
                })
            elif "complaint" in prompt_str:
                default_content = json.dumps({
                    "is_sensitive": False,
                    "sensitive_notice": None,
                    "guidance": "Empathetic acknowledgment of the viewer's frustration with a constructive next step.",
                    "sample_response": "We apologize for the inconvenience! We are actively reviewing this and will have an update soon.",
                })
            elif "praise" in prompt_str:
                default_content = json.dumps({
                    "is_sensitive": False,
                    "sensitive_notice": None,
                    "guidance": "Warm, authentic appreciation to reinforce viewer loyalty.",
                    "sample_response": "Thank you so much! Really glad you enjoyed the tutorial!",
                })
            else:
                default_content = json.dumps({
                    "is_sensitive": False,
                    "sensitive_notice": None,
                    "guidance": "Helpful and friendly reply aligned with channel tone.",
                    "sample_response": "Thank you for the question! Please check the video notes and linked repository for detailed guidance.",
                })

        # 3. Grounded Drafter Prompt
        elif "user question:" in prompt_str or ("retrieved video transcript" in prompt_str and "draft reply:" in prompt_str):
            q_text = prompt_str.split("user question:")[-1] if "user question:" in prompt_str else prompt_str
            if "python version" in q_text:
                default_content = "According to the tutorial at [01:15], Python 3.10 or higher is required."
            elif "podman" in q_text:
                default_content = "Yes! As explained at [02:45], you can alias podman-compose for Docker Compose seamlessly."
            elif "pgvector" in q_text:
                default_content = "As demonstrated at [03:10], you can install pgvector using the official Docker image with CREATE EXTENSION vector."
            elif any(k in q_text for k in ["ios", "streaming", "websockets", "aws", "lambda", "pricing"]):
                default_content = "ABSTAIN"
            else:
                default_content = "ABSTAIN"

        # 3. Verifier Judge Prompt
        elif "faithfulness" in prompt_str or "judge" in prompt_str:
            if "abstain" in prompt_str:
                default_content = "0.10\nDraft correctly abstained from ungrounded claims."
            else:
                default_content = "0.95\nClaim fully supported by transcript context at cited timestamp."

        # 4. Default Generic Fallback
        else:
            if any(k in prompt_str for k in ["draft", "reply", "transcript", "grounding", "tone"]):
                default_content = "Thank you for asking! Please check the relevant section in the reference documentation."
            else:
                default_content = json.dumps({
                    "category": "question",
                    "confidence": 0.95,
                    "rationale": "Viewer is inquiring about project requirements.",
                    "sensitive": False,
                })
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": default_content,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 35,
                "total_tokens": 50,
            },
            "model": model,
        }

    def reset(self) -> None:
        self.call_history.clear()
        self._preset_responses.clear()

