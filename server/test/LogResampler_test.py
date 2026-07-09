"""Phase 3.3 (F6): resampling a mixed daily/weekly BodyLog history into the
one-row-per-week shape the engine needs, and the symmetric daily-view
expansion."""

import unittest
from datetime import date, datetime, timedelta, timezone

from server.src.data.domain.BodyLog import BodyLog
from server.src.services.LogResampler import daily_view, is_computable, resample_to_weekly

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

    def test_macros_average_only_days_that_logged_them(self):
        """Phase 3.4, F9: average whatever days logged macros (minimum 1),
        not the full week -- same graceful-degradation idea as weight's
        median."""
        week = [
            make_log(60, date(2026, 1, 5), granularity="daily", carbs_g=200.0, fat_g=60.0, protein_g=150.0),
            make_log(61, date(2026, 1, 6), granularity="daily"),  # no macros logged this day
            make_log(62, date(2026, 1, 7), granularity="daily", carbs_g=220.0, fat_g=80.0, protein_g=170.0),
        ]
        result = resample_to_weekly(week)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].carbs_g, 210.0)
        self.assertAlmostEqual(result[0].fat_g, 70.0)
        self.assertAlmostEqual(result[0].protein_g, 160.0)

    def test_macros_are_none_when_no_day_in_the_week_logged_them(self):
        week = [
            make_log(70, date(2026, 1, 5), granularity="daily"),
            make_log(71, date(2026, 1, 6), granularity="daily"),
        ]
        result = resample_to_weekly(week)
        self.assertIsNone(result[0].carbs_g)
        self.assertIsNone(result[0].fat_g)
        self.assertIsNone(result[0].protein_g)

    def test_partial_days_average_only_the_days_that_logged_each_field(self):
        """Phase 7.4 (partial logs, see README): the same graceful-
        degradation rule Phase 3.4 gave the macro trio now applies to
        weight/waist/neck/intake/steps too -- e.g. a Mi Fitness-only sync
        day (steps, no weight) alongside a Samsung Health-only day
        (intake, no weight/steps) alongside a manually-completed day
        (everything)."""
        week = [
            make_log(80, date(2026, 1, 5), granularity="daily", weight_kg=None, waist_cm=None,
                     neck_cm=None, intake_kcal=None, steps=7000.0),  # Mi Fitness only
            make_log(81, date(2026, 1, 6), granularity="daily", weight_kg=None, waist_cm=None,
                     neck_cm=None, steps=None, intake_kcal=2100.0),  # Samsung Health only
            make_log(82, date(2026, 1, 7), granularity="daily", weight_kg=90.0, waist_cm=80.0,
                     neck_cm=35.0, intake_kcal=2200.0, steps=6500.0),  # completed manually
        ]
        result = resample_to_weekly(week)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row.weight_kg, 90.0)  # median of the one day that has it
        self.assertEqual(row.waist_cm, 80.0)
        self.assertEqual(row.neck_cm, 35.0)
        self.assertAlmostEqual(row.intake_kcal, 2150.0)  # mean of 2100/2200
        self.assertAlmostEqual(row.steps, 6750.0)  # mean of 7000/6500
        self.assertTrue(is_computable(row))

    def test_field_is_none_when_no_day_in_the_week_ever_logged_it(self):
        week = [
            make_log(90, date(2026, 1, 5), granularity="daily", weight_kg=None, waist_cm=None,
                     neck_cm=None, steps=7000.0),
            make_log(91, date(2026, 1, 6), granularity="daily", weight_kg=None, waist_cm=None,
                     neck_cm=None, steps=6800.0),
        ]
        result = resample_to_weekly(week)
        row = result[0]
        self.assertIsNone(row.weight_kg)
        self.assertIsNone(row.waist_cm)
        self.assertIsNone(row.neck_cm)
        self.assertFalse(is_computable(row))

    def test_intake_is_real_ignores_days_that_never_logged_intake(self):
        week = [
            make_log(100, date(2026, 1, 5), granularity="daily", intake_kcal=None),
            make_log(101, date(2026, 1, 6), granularity="daily", intake_kcal=2200.0, intake_is_real=False),
        ]
        result = resample_to_weekly(week)
        # Only day 101 actually logged intake, and it wasn't real.
        self.assertFalse(result[0].intake_is_real)

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


class IsComputableTest(unittest.TestCase):
    def test_complete_row_is_computable(self):
        self.assertTrue(is_computable(make_log(1, date(2026, 1, 1))))

    def test_missing_any_one_of_the_five_required_fields_is_not_computable(self):
        for field in ("weight_kg", "waist_cm", "neck_cm", "intake_kcal", "steps"):
            with self.subTest(field=field):
                log = make_log(1, date(2026, 1, 1), **{field: None})
                self.assertFalse(is_computable(log))


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
