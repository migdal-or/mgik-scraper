"""
Publication Pattern Prediction Module

Analyzes historical publication patterns to predict optimal check intervals.
Returns coefficient (0.1-1.0) based on how current time matches patterns.
"""

from datetime import datetime
from typing import Dict
import logging
from datastore import DecisionsDatabase

logger = logging.getLogger("mgik-scraper")


class PublicationPredictor:
    """
    Analyzes historical publication patterns to predict optimal check frequency.

    Returns coefficient (0.1 - 1.0) based on how well current time matches patterns:
    - 0.1 = highly active period (check 10x more frequently)
    - 1.0 = no pattern match (use base interval)
    """

    def __init__(self, db: DecisionsDatabase, base_interval: int):
        """
        Initialize predictor with database and base interval.

        Args:
            db: Database instance for querying timestamps
            base_interval: Base interval from config (SCHEDULER_DEFAULT_INTERVAL)
        """
        self.db = db
        self.base_interval = base_interval
        logger.info("Predictor initialized: base_interval=%ss", base_interval)

    def get_coefficient(self) -> float:
        """
        Calculate prediction coefficient for current datetime.

        Returns:
            float: Coefficient between 0.1 (very active) and 1.0 (quiet)
        """
        current_time = datetime.now()
        patterns = self.analyze_patterns()

        # Calculate match score for current time
        score = self._calculate_match_score(current_time, patterns)

        # Convert score to coefficient (inverse relationship)
        # High score → low coefficient (check more often)
        # Low score → high coefficient (check less often)
        coefficient = max(0.1, 1.0 - (score * 0.9))

        logger.debug(
            "Prediction: score=%.2f, coefficient=%.2f (hour=%d, dow=%d, dom=%d, doy=%d)",
            score,
            coefficient,
            current_time.hour,
            current_time.weekday(),
            current_time.day,
            current_time.timetuple().tm_yday,
        )

        return coefficient

    def analyze_patterns(self) -> Dict:
        """
        Analyze both decision dates and fetch timestamps.

        Returns dict with:
        - decision_patterns: When decisions are published (from 'date' field)
        - fetch_patterns: When we discover them (from 'fetched_at' field)

        Each pattern includes:
        - hour: [count0, count1, ..., count23]
        - dow: [countMon, countTue, ..., countSun]
        - dom: [count1, count2, ..., count31]
        - doy: [count1, count2, ..., count365]
        """
        timestamps = self.db.get_publication_timestamps(limit=1000)

        decision_patterns = self._build_pattern_dict()
        fetch_patterns = self._build_pattern_dict()

        for item in timestamps:
            # Analyze decision publication date
            if item["date"]:
                try:
                    decision_dt = datetime.fromisoformat(item["date"])
                    self._update_pattern(decision_patterns, decision_dt)
                except (ValueError, TypeError) as e:
                    logger.debug(
                        "Failed to parse decision date %s: %s", item["date"], e
                    )

            # Analyze when we fetched it
            if item["fetched_at"]:
                try:
                    fetch_dt = datetime.fromisoformat(item["fetched_at"])
                    self._update_pattern(fetch_patterns, fetch_dt)
                except (ValueError, TypeError) as e:
                    logger.debug(
                        "Failed to parse fetched_at %s: %s", item["fetched_at"], e
                    )

        logger.debug(
            "Pattern analysis: %d records, decision_samples=%d, fetch_samples=%d",
            len(timestamps),
            sum(decision_patterns["hour"]),
            sum(fetch_patterns["hour"]),
        )

        return {"decision": decision_patterns, "fetch": fetch_patterns}

    def _build_pattern_dict(self) -> Dict:
        """Create empty pattern distribution dictionary"""
        return {
            "hour": [0] * 24,  # Hour of day
            "dow": [0] * 7,  # Day of week (0=Monday, 6=Sunday)
            "dom": [0] * 31,  # Day of month (1-31)
            "doy": [0] * 366,  # Day of year (1-366, leap year safe)
        }

    def _update_pattern(self, patterns: Dict, dt: datetime):
        """Increment counters for given datetime"""
        patterns["hour"][dt.hour] += 1
        patterns["dow"][dt.weekday()] += 1
        patterns["dom"][dt.day - 1] += 1  # Convert 1-31 to 0-30
        patterns["doy"][dt.timetuple().tm_yday - 1] += 1  # Convert 1-366 to 0-365

    def _calculate_match_score(self, dt: datetime, patterns: Dict) -> float:
        """
        Calculate how well current datetime matches historical patterns.

        Returns score 0.0 (no match) to 1.0 (perfect match).

        Weighted average of:
        - Hour match (40%): Current hour activity vs max
        - Day-of-week match (20%): Current dow activity vs max
        - Day-of-month match (20%): Current dom activity vs max
        - Day-of-year match (20%): Current doy activity vs max
        """
        # Use decision patterns (when decisions are published)
        # as primary indicator
        dec = patterns["decision"]

        # Normalize each dimension (0-1 scale)
        hour_score = self._normalize(dec["hour"][dt.hour], dec["hour"])
        dow_score = self._normalize(dec["dow"][dt.weekday()], dec["dow"])
        dom_score = self._normalize(dec["dom"][dt.day - 1], dec["dom"])
        doy_score = self._normalize(dec["doy"][dt.timetuple().tm_yday - 1], dec["doy"])

        # Weighted average (hour most important, doy for seasonal patterns)
        score = hour_score * 0.4 + dow_score * 0.2 + dom_score * 0.2 + doy_score * 0.2

        return score

    def _normalize(self, value: int, distribution: list) -> float:
        """Normalize value against distribution (0-1 scale)"""
        max_val = max(distribution) if distribution else 1
        return value / max_val if max_val > 0 else 0.0
