"""DataForSEO HTTP client + cost tracking.

The full client (HTTP + endpoints) is added in Task 7. This file currently
provides the CostTracker and DataForSEOBudgetExceeded exception, used by
the HTTP wrapper to enforce per-run budget caps.
"""

from collections import deque
from dataclasses import dataclass, field


class DataForSEOBudgetExceeded(RuntimeError):
    """Raised when the per-run cost or call cap is exceeded."""


@dataclass
class CostTracker:
    max_cost: float
    max_calls: int
    total_cost: float = 0.0
    total_calls: int = 0
    _recent: deque = field(default_factory=lambda: deque(maxlen=5))

    def record(self, *, cost: float, endpoint: str) -> None:
        prospective_cost = self.total_cost + cost
        prospective_calls = self.total_calls + 1

        if prospective_cost > self.max_cost:
            raise DataForSEOBudgetExceeded(
                f"DataForSEO cost cap of ${self.max_cost:.2f} would be exceeded "
                f"(current ${self.total_cost:.4f} + ${cost:.4f}); "
                f"recent endpoints: {list(self._recent)}"
            )
        if prospective_calls > self.max_calls:
            raise DataForSEOBudgetExceeded(
                f"DataForSEO call cap of {self.max_calls} would be exceeded "
                f"(current {self.total_calls} + 1); "
                f"recent endpoints: {list(self._recent)}"
            )

        self.total_cost = prospective_cost
        self.total_calls = prospective_calls
        self._recent.append(endpoint)
