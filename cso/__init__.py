"""
Credit Spread Optimizer package.

Re-exports key classes for convenience.
"""

from .models import CreditSpread, SpreadType, ScreeningCriteria, OptimizationWeights, ScreeningResult
from .filters import passes_all_filters, get_failed_filters, apply_all_filters
from .analyzers import SpreadAnalyzer, IVAnalyzer, ThetaAnalyzer, ProbabilityAnalyzer, ExpectedValueAnalyzer
from .spread_optimizer import SpreadOptimizer, SpreadComparator
from .spread_screener import CreditSpreadScreener, create_mock_spread
from .disciplined_models import (
    CreditSpreadCandidate, TradeRecommendation, HardFilterResult,
    RejectionReason, ScreeningConfig
)
from .disciplined_screener import DisciplinedScreener, create_candidate_from_strikes, get_current_vix
