"""Phase 3.3 (F6): resampling a mixed daily/weekly BodyLog history into the
one-row-per-week shape the engine needs, and the symmetric daily-view
expansion."""

import unittest
from datetime import date, datetime, timedelta, timezone

from server.src.data.domain.BodyLog import BodyLog
from server.src.services.LogResampler import daily_view, resample_to_weekly

CREATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_log(log_id, log_date, granularity="weekly", **overrides) -> BodyLog:
    defaults = dict(
        log_id=log_id,
        user_id=1,
        date=log_date,
        weight_kg=90.0,
        waist_cm=90.0,
        neck_cm=38.0,
        intake_kcal=2200.0,
        intake_is_real=True,
        steps=6000.0,
        cardio_kcal=0.0,
        source="real",
        created_at=CREATED_AT,
        granularity=granularity,
    )
    defaults.update(overrides)
    return BodyLog(**defaults)


class ResampleToWeeklyTest(unittest.TestCase):
    def test_weekly_only_history_passes_through_unchanged(self):
        logs = [
            make_log(1, date(2026, 1, 4), weight_kg=97.0),
            make_log(2, date(2026, 1, 11), weight_kg=96.5),
            make_log(3, date(2026, 1, 18), weight_kg=96.0),
        ]
        result = resample_to_weekly(logs)
        self.assertEqual(result, sorted(logs, key=lambda log: log.date))

    def test_full_daily_week_collapses_with_median_and_mean(self):
        # ISO week 2026-W02: Mon 2026-01-05 .. Sun 2026-01-11.
        week = [
            make_log(
                10 + i,
                date(2026, 1, 5) + timedelta(days=i),
                granularity="daily",
                weight_kg=90.0 + i,  # 90..96, median = 93.0
                steps=5000.0 + i * 100,  # mean = 5000+300=5300
                cardio_kcal=100.0 + i * 10,  # mean = 100+30=130
                waist_cm=88.0 + i,  # mean = 91.0
                neck_cm=37.0 + i,  # mean = 40.0
                intake_kcal=2000.0 + i * 10,  # mean = 2000+30=2030
            )
            for i in range(7)
        ]
        result = resample_to_weekly(week)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row.weight_kg, 93.0)
        self.assertAlmostEqual(row.steps, 5300.0)
        self.assertAlmostEqual(row.cardio_kcal, 130.0)
        self.assertAlmostEqual(row.waist_cm, 91.0)
        self.assertAlmostEqual(row.neck_cm, 40.0)
        self.assertAlmostEqual(row.intake_kcal, 2030.0)
        self.assertEqual(row.date, date(2026, 1, 11))
        self.assertEqual(row.log_id, week[-1].log_id)
        self.assertTrue(row.intake_is_real)

    def test_intake_is_real_is_and_reduced_across_the_week(self):
        week = [
            make_log(20, date(2026, 1, 5), granularity="daily", intake_is_real=True),
            make_log(21, date(2026, 1, 6), granularity="daily", intake_is_real=False),
            make_log(22, date(2026, 1, 7), granularity="daily", intake_is_real=True),
        ]
        result = resample_to_weekly(week)
        self.assertFalse(result[0].intake_is_real)

    def test_partial_week_still_resamples_gracefully(self):
        week = [
            make_log(30, date(2026, 1, 5), granularity="daily", weight_kg=90.0),
            make_log(31, date(2026, 1, 6), granularity="daily", weight_kg=91.0),
            make_log(32, date(2026, 1, 7), granularity="daily", weight_kg=92.0),
        ]
        result = resample_to_weekly(week)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].weight_kg, 91.0)

    def test_lone_daily_row_degrades_to_its_own_value(self):
        logs = [make_log(40, date(2026, 1, 5), granularity="daily", weight_kg=88.5)]
        result = resample_to_weekly(logs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].weight_kg, 88.5)
        self.assertEqual(result[0].log_id, 40)

    def test_mixed_account_resolves_each_week_independently(self):
        weekly_row = make_log(1, date(2025, 12, 28), granularity="weekly", weight_kg=97.0)
        daily_week = [
            make_log(50, date(2026, 1, 5), granularity="daily", weight_kg=95.0),
            make_log(51, date(2026, 1, 7), granularity="daily", weight_kg=96.0),
        ]
        result = resample_to_weekly([weekly_row] + daily_week)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], weekly_row)
        self.assertEqual(result[1].weight_kg, 95.5)
        self.assertEqual(result[1].date, date(2026, 1, 7))


class DailyViewTest(unittest.TestCase):
    def test_weekly_log_expands_across_days_since_previous_log(self):
        logs = [
            make_log(1, date(2026, 1, 4), granularity="weekly", weight_kg=97.0, steps=6000, cardio_kcal=0),
            make_log(2, date(2026, 1, 11), granularity="weekly", weight_kg=96.5, steps=6200, cardio_kcal=100),
        ]
        points = daily_view(logs)
        # First log has no previous anchor -> emits just its own day.
        self.assertEqual(points[0].day, date(2026, 1, 4))
        second_week = [p for p in points if date(2026, 1, 5) <= p.day <= date(2026, 1, 11)]
        self.assertEqual(len(second_week), 7)
        for point in second_week:
            self.assertEqual(point.weight_kg, 96.5)
            self.assertEqual(point.steps, 6200)
            self.assertEqual(point.cardio_kcal, 100)
            self.assertEqual(point.source_log_id, 2)

    def test_daily_log_emits_itself_only_no_expansion(self):
        logs = [make_log(1, date(2026, 1, 5), granularity="daily", weight_kg=90.0)]
        points = daily_view(logs)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].day, date(2026, 1, 5))
        self.assertEqual(points[0].weight_kg, 90.0)


if __name__ == "__main__":
    unittest.main()
