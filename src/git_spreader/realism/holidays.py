"""Holiday slot modifier — removes holiday dates from available time slots."""

from __future__ import annotations

import random
from datetime import date

import holidays as holidays_lib

from git_spreader.models import SpreaderConfig, TimeSlot
from git_spreader.realism import register_slot


@register_slot
class HolidayModifier:
    """Removes time slots that fall on holidays."""

    def is_enabled(self, config: SpreaderConfig) -> bool:
        return config.avoid_holidays

    def modify_slots(
        self,
        slots: list[TimeSlot],
        config: SpreaderConfig,
        rng: random.Random,
    ) -> list[TimeSlot]:
        holiday_dates = self._get_holiday_dates(slots, config)
        return [s for s in slots if s.start.date() not in holiday_dates]

    def _get_holiday_dates(self, slots: list[TimeSlot], config: SpreaderConfig) -> set[date]:
        if not slots:
            return set()

        years = {s.start.year for s in slots}
        holiday_dates: set[date] = set()

        try:
            for year in years:
                cal = holidays_lib.country_holidays(config.holiday_calendar, years=year)
                holiday_dates.update(cal.keys())
        except NotImplementedError:
            pass  # Unknown calendar — skip silently

        # Add custom holiday dates
        for date_str in config.holiday_additional:
            try:
                holiday_dates.add(date.fromisoformat(date_str))
            except ValueError:
                pass

        return holiday_dates
