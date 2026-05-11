"""Pairs trading strategy components.

Module map
----------
- :mod:`strategy.cointegration` - Engle-Granger and Johansen tests.
- :mod:`strategy.pair_selection` - cross-industry pair screening with
  half-life filtering.
- :mod:`strategy.zscore_signal` - rolling Z-score signal generator.
- :mod:`strategy.dollar_neutral` - Beta-neutral, dollar-neutral position sizing.
"""

from strategy.cointegration import CointegrationResult, engle_granger, half_life  # noqa: F401
from strategy.dollar_neutral import build_positions  # noqa: F401
from strategy.pair_selection import PairCandidate, screen_pairs  # noqa: F401
from strategy.zscore_signal import generate_signals  # noqa: F401
