"""Event-driven risk overlay.

When the LLM RAG agent flags a high-risk event for a stock, the overlay can:

- **Force-flat** any pair that contains that stock for ``cooldown_days``.
- **Reduce** the pair's notional by a configurable factor (default 0).

The overlay is applied *after* the Z-score signal but *before* position sizing,
so it never deepens an existing position - it only blocks or shrinks new
exposures and exits open positions.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.logger import get_logger

log = get_logger(__name__)


# Mapping from taxonomy key -> default severity weight used when the agent
# omits an explicit severity.  Higher = more disruptive.
DEFAULT_SEVERITY: dict[str, float] = {
    "suspension":          1.0,
    "fraud_investigation": 1.0,
    "restructure":         0.7,
    "private_placement":   0.5,
    "earnings_warning":    0.7,
    "shareholder_reduction": 0.4,
    "litigation":          0.5,
    "equity_change":       0.5,
    "other":               0.1,
}


@dataclass
class EventRiskOverlay:
    """Apply event-driven throttling to a per-pair position series.

    Parameters
    ----------
    cooldown_days
        Trading days the throttle stays active after an event.
    flat_threshold
        Severity above which we force-flat the position (default 0.7).
    reduce_threshold
        Severity above which we reduce position size by ``reduce_factor``.
    reduce_factor
        Multiplier applied when in the *reduce* band (e.g. 0.3 = keep 30%).
    """

    cooldown_days: int = 5
    flat_threshold: float = 0.7
    reduce_threshold: float = 0.4
    reduce_factor: float = 0.3

    def apply(
        self,
        positions: pd.DataFrame,
        events: pd.DataFrame,
        codes: tuple[str, str],
    ) -> pd.DataFrame:
        """Return a new positions frame with throttling applied.

        Parameters
        ----------
        positions
            DataFrame indexed by date with at least a ``pos`` column.
        events
            Long-format event frame with columns
            ``ts_code, event_date, event_type, severity``.
        codes
            ``(code_a, code_b)`` to filter relevant events.
        """
        if positions.empty:
            return positions
        rel = events[events["ts_code"].isin(codes)].copy() if not events.empty else pd.DataFrame()
        if rel.empty:
            return positions.copy()

        rel["event_date"] = pd.to_datetime(rel["event_date"])
        rel = rel.sort_values("event_date")

        # Build per-date severity by taking the max-severity event in the
        # cooldown window.
        idx = pd.to_datetime(positions.index)
        sev = pd.Series(0.0, index=idx)
        for _, row in rel.iterrows():
            etype = str(row.get("event_type", "other"))
            raw_sev = float(row.get("severity") or DEFAULT_SEVERITY.get(etype, 0.1))
            start = pd.Timestamp(row["event_date"])
            end = start + pd.Timedelta(days=int(self.cooldown_days) * 2)  # weekends pad
            mask = (idx >= start) & (idx <= end)
            sev.loc[mask] = sev.loc[mask].clip(lower=raw_sev)

        out = positions.copy()
        scale = pd.Series(1.0, index=positions.index)
        scale[sev.values >= self.flat_threshold] = 0.0
        in_reduce = (sev.values >= self.reduce_threshold) & (sev.values < self.flat_threshold)
        scale[in_reduce] = self.reduce_factor

        for col in ("pos", "w_a", "w_b"):
            if col in out.columns:
                out[col] = out[col] * scale.values

        log.debug(
            "risk overlay applied for {}: flat_days={}, reduce_days={}",
            codes,
            int((scale == 0).sum()),
            int((scale == self.reduce_factor).sum()),
        )
        return out
