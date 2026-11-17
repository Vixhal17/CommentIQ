from datetime import datetime, timezone, date
from typing import Optional
from backend.app.core.logging import logger

class BudgetExceededException(Exception):
    """Raised when the daily token usage budget is exhausted."""
    pass


class TokenBudgetGuard:
    """
    Guards free-tier API limits by tracking cumulative daily token usage.
    Automatically resets when a new UTC day begins.
    """

    def __init__(self, daily_limit: int = 100000):
        self.daily_limit = daily_limit
        self._current_date: date = datetime.now(timezone.utc).date()
        self._tokens_used_today: int = 0

    def _check_and_reset_day(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self._current_date:
            logger.info(f"New UTC day detected. Resetting token budget from {self._tokens_used_today} to 0.")
            self._current_date = today
            self._tokens_used_today = 0

    @property
    def tokens_used_today(self) -> int:
        self._check_and_reset_day()
        return self._tokens_used_today

    @property
    def tokens_remaining(self) -> int:
        self._check_and_reset_day()
        return max(0, self.daily_limit - self._tokens_used_today)

    def check_budget_available(self, estimated_tokens: int = 500) -> None:
        """
        Verify that making a request with the estimated tokens will not violate the budget.
        """
        self._check_and_reset_day()
        if self._tokens_used_today + estimated_tokens > self.daily_limit:
            msg = (
                f"Daily token budget exceeded! Limit: {self.daily_limit}, "
                f"Used: {self._tokens_used_today}, Requested: {estimated_tokens}. "
                "Stopping gracefully to protect free tier limits."
            )
            logger.error(msg)
            raise BudgetExceededException(msg)

    def record_usage(self, actual_tokens: int) -> None:
        """
        Add consumed tokens to today's tally.
        """
        self._check_and_reset_day()
        self._tokens_used_today += max(0, actual_tokens)
        logger.info(
            f"Recorded {actual_tokens} tokens. Total today: {self._tokens_used_today}/{self.daily_limit} "
            f"({self.tokens_remaining} remaining)"
        )

