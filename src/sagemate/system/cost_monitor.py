"""LLM Token & Cost Monitoring Module.

Tracks all LLM API calls with token counts and estimated costs.
Stores data in SQLite for persistent tracking and API querying.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# Model Pricing (per 1M tokens, USD)
# ============================================================
# Prices are approximate and may vary by provider.
# Update this dict when adding new models.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_price_per_1m, output_price_per_1m)
    # Qwen family (DashScope)
    "qwen-plus": (0.8, 2.0),
    "qwen-turbo": (0.3, 0.6),
    "qwen-max": (20.0, 20.0),
    "qwen3.6-plus": (0.8, 2.0),
    # GLM family (BigModel)
    "glm-4": (5.0, 5.0),
    "glm-4v-plus": (5.0, 5.0),
    "glm-5": (5.0, 5.0),
    # Default fallback
    "default": (10.0, 20.0),
}


@dataclass
class CostEntry:
    """A single LLM call record."""
    id: int = 0
    timestamp: str = ""
    model: str = ""
    purpose: str = ""          # "compile", "query", "router", "recompile"
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    success: bool = True
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "model": self.model,
            "purpose": self.purpose,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "duration_ms": round(self.duration_ms, 1),
            "success": self.success,
            "error": self.error,
        }


class CostMonitor:
    """Persistent LLM cost tracker."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            from ..core.config import settings
            db_path = settings.data_dir / "cost_monitor.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cost_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    model TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    cost_usd REAL NOT NULL DEFAULT 0.0,
                    duration_ms REAL NOT NULL DEFAULT 0.0,
                    success INTEGER NOT NULL DEFAULT 1,
                    error TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cost_timestamp
                ON cost_log(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cost_purpose
                ON cost_log(purpose)
            """)

    def record(
        self,
        model: str,
        purpose: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        duration_ms: float = 0.0,
        success: bool = True,
        error: str = "",
    ) -> CostEntry:
        """Record a single LLM call."""
        total = input_tokens + output_tokens
        cost = self._estimate_cost(model, input_tokens, output_tokens)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        entry = CostEntry(
            timestamp=ts,
            model=model,
            purpose=purpose,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            cost_usd=cost,
            duration_ms=duration_ms,
            success=success,
            error=error,
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO cost_log
                   (timestamp, model, purpose, input_tokens, output_tokens,
                    total_tokens, cost_usd, duration_ms, success, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ts, model, purpose, input_tokens, output_tokens,
                 total, cost, duration_ms, int(success), error),
            )

        logger.info(
            f"📊 Cost: {model} ({purpose}) | "
            f"in={input_tokens:,} out={output_tokens:,} total={total:,} | "
            f"${cost:.6f} | {duration_ms:.0f}ms"
        )
        return entry

    def _estimate_cost(
        self, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Estimate cost in USD based on model pricing."""
        in_price, out_price = MODEL_PRICING.get(
            model.lower(), MODEL_PRICING["default"]
        )
        return (input_tokens / 1_000_000 * in_price +
                output_tokens / 1_000_000 * out_price)

    def get_summary(self, days: int = 30) -> dict:
        """Get cost summary for the last N days."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT
                       COUNT(*) as total_calls,
                       COALESCE(SUM(input_tokens), 0) as total_input,
                       COALESCE(SUM(output_tokens), 0) as total_output,
                       COALESCE(SUM(total_tokens), 0) as total_tokens,
                       COALESCE(SUM(cost_usd), 0) as total_cost,
                       COALESCE(AVG(duration_ms), 0) as avg_duration_ms
                   FROM cost_log
                   WHERE timestamp >= datetime('now', '-{} days')
                   AND success = 1""".format(days),
            ).fetchone()

            # Breakdown by purpose
            purpose_rows = conn.execute(
                """SELECT purpose,
                          COUNT(*) as calls,
                          COALESCE(SUM(total_tokens), 0) as tokens,
                          COALESCE(SUM(cost_usd), 0) as cost
                   FROM cost_log
                   WHERE timestamp >= datetime('now', '-{} days')
                   AND success = 1
                   GROUP BY purpose
                   ORDER BY cost DESC""".format(days),
            ).fetchall()

            # Breakdown by model
            model_rows = conn.execute(
                """SELECT model,
                          COUNT(*) as calls,
                          COALESCE(SUM(total_tokens), 0) as tokens,
                          COALESCE(SUM(cost_usd), 0) as cost
                   FROM cost_log
                   WHERE timestamp >= datetime('now', '-{} days')
                   AND success = 1
                   GROUP BY model
                   ORDER BY cost DESC""".format(days),
            ).fetchall()

        return {
            "period_days": days,
            "total_calls": rows["total_calls"],
            "total_input_tokens": rows["total_input"],
            "total_output_tokens": rows["total_output"],
            "total_tokens": rows["total_tokens"],
            "total_cost_usd": round(rows["total_cost"], 4),
            "avg_duration_ms": round(rows["avg_duration_ms"], 1),
            "by_purpose": [dict(r) for r in purpose_rows],
            "by_model": [dict(r) for r in model_rows],
        }

    def get_recent_entries(self, limit: int = 20) -> list[dict]:
        """Get recent cost log entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM cost_log
                   ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
