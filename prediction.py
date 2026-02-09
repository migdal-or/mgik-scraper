"""
Publication Pattern Prediction Module

Analyzes historical publication patterns to predict optimal check intervals.
Returns coefficient (0.1-1.0) based on how current time matches patterns.
"""

from datetime import datetime
from datetime import date
from typing import Dict
from typing import Union
import logging
from datastore import DecisionsDatabase
from datastore import mgik_timezone

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

        Score = sum of historical counts matching current time dimensions.
        Higher score = more historical activity = higher coefficient.
        Interval is divided by coefficient (higher coef = shorter interval).

        Returns:
            float: Coefficient (raw score, minimum 1.0 to avoid division issues)
        """
        current_time = datetime.now(mgik_timezone)
        patterns = self.analyze_patterns()

        score = self._calculate_match_score(current_time, patterns)
        coefficient = max(1.0, score)

        logger.debug(
            "Prediction: coefficient=%.1f (hour=%d, dow=%d, dom=%d, month=%d, doy=%d)",
            coefficient,
            current_time.hour,
            current_time.weekday(),
            current_time.day,
            current_time.month,
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
        timestamps = self.db.get_publication_timestamps()

        decision_patterns = self._build_pattern_dict()
        fetch_patterns = self._build_pattern_dict()

        for item in timestamps:
            # Analyze decision publication date
            if item["date"]:
                try:
                    # item["date"] is typically just a date string "2025-01-15"
                    decision_dt = date.fromisoformat(item["date"])
                    self._update_pattern(decision_patterns, decision_dt)
                except (ValueError, TypeError) as e:
                    logger.debug(
                        "Failed to parse decision date %s: %s", item["date"], e
                    )

            # Analyze when we fetched it
            if item["fetched_at"]:
                try:
                    # fetched_at is a full datetime string
                    fetch_dt = datetime.fromisoformat(item["fetched_at"])
                    self._update_pattern(fetch_patterns, fetch_dt)
                except (ValueError, TypeError) as e:
                    logger.debug(
                        "Failed to parse fetched_at %s: %s", item["fetched_at"], e
                    )

        dec_total = sum(sum(v) for v in decision_patterns.values())
        fetch_total = sum(sum(v) for v in fetch_patterns.values())

        logger.debug(
            "Pattern analysis: %d records, decision_samples=%d, fetch_samples=%d",
            len(timestamps),
            dec_total,
            fetch_total,
        )

        return {"decision": decision_patterns, "fetch": fetch_patterns}

    def _build_pattern_dict(self) -> Dict:
        """Create empty pattern distribution dictionary"""
        return {
            "hour": [0] * 24,  # Hour of day (0-23)
            "dow": [0] * 7,  # Day of week (0=Monday, 6=Sunday)
            "dom": [0] * 31,  # Day of month (1-31)
            "month": [0] * 12,  # Month of year (1-12)
            "doy": [0] * 366,  # Day of year (1-366, leap year safe)
        }

    def _update_pattern(self, patterns: Dict, dt: Union[date, datetime]):
        """
        Increment counters for given date or datetime.

        For date objects: dow/dom/month/doy are incremented (no hour info).
        For datetime objects: all fields including hour are incremented.
        """
        # Only increment hour patterns if we have datetime with hour info
        if isinstance(dt, datetime):
            patterns["hour"][dt.hour] += 1

        patterns["dow"][dt.weekday()] += 1
        patterns["dom"][dt.day - 1] += 1  # Convert 1-31 to 0-30
        patterns["month"][dt.month - 1] += 1  # Convert 1-12 to 0-11
        yday = dt.timetuple().tm_yday
        patterns["doy"][yday - 1] += 1  # Convert 1-366 to 0-365

    def _calculate_match_score(self, dt: datetime, patterns: Dict) -> float:
        """
        Calculate match score by summing counts from BOTH patterns.

        Uses both decision patterns (when published) and fetch patterns (when discovered).
        For each dimension, sum the counts from both patterns.

        Returns:
            float: Sum of all matching counts
        """
        dec = patterns["decision"]
        fetch = patterns["fetch"]

        hour_count = dec["hour"][dt.hour] + fetch["hour"][dt.hour]
        dow_count = dec["dow"][dt.weekday()] + fetch["dow"][dt.weekday()]
        dom_index = dt.day - 1
        dom_count = dec["dom"][dom_index] + fetch["dom"][dom_index]
        month_index = dt.month - 1
        month_count = dec["month"][month_index] + fetch["month"][month_index]
        yday = dt.timetuple().tm_yday
        doy_index = yday - 1
        doy_count = dec["doy"][doy_index] + fetch["doy"][doy_index]

        score = hour_count + dow_count + dom_count + month_count + doy_count

        return float(score)
