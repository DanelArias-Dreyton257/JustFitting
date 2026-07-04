"""Energy reconciliation (Phase 3.2, F5): each test builds the minimal
`BodyLog`-like/`CompositionResult` series needed, since
`EnergyReconciliation.compute_energy_reconciliation` only reads a handful of
fields from each (see the module's docstring)."""

import unittest
from dataclasses import dataclass
from datetime import date, timedelta

from server.src.services.composition.EnergyReconciliation import (
    compute_energy_reconciliation,
)
from server.src.services.composition.models import CompositionResult, EngineConstants

BASE_DATE = date(2026, 1, 4)


@dataclass
class FakeLog:
    date: date
    intake_kcal: float
    intake_is_real: bool = True


def make_result(week_offset: int = 0, **overrides) -> CompositionResult:
    defaults = dict(
        date=BASE_DATE + timedelta(days=7 * week_offset),
        age=24,
        bmi=28.0,
        ffmi=22.0,
        ffmi_adj=22.0,
        rfm=0.2,
        navy=0.2,
        deurenberg=0.2,
        body_fat=0.2,
        fat_mass_kg=18.0,
        lean_mass_kg=72.0,
        above_target=0.05,
        bmr=2000.0,
        neat=200.0,
        tdee=2400.0,
        target_calories=2000.0,
        intake_diff=0.0,
        weight_delta_kg=0.0,
        weight_delta_pct=0.0,
        weight_objective_kg=90.0,
        weight_gap_kg=0.0,
        weight_to_shed_kg=0.0,
        weekly_deficit_kcal=0.0,
        daily_deficit_kcal=0.0,
        final_weight_kg=85.0,
        weeks_to_goal=10.0,
        source="real",
    )
    defaults.update(overrides)
    return CompositionResult(**defaults)


class EnergyReconciliationTest(unittest.TestCase):
    def test_last_week_has_no_tissue_surplus_or_error_yet(self):
        logs = [FakeLog(BASE_DATE, 2400.0)]
        results = [make_result(0, tdee=2400.0)]
        rows = compute_energy_reconciliation(logs, results)
        self.assertIsNotNone(rows[0].surplus_ingested_kcal)
        self.assertIsNone(rows[0].surplus_tissue_kcal)
        self.assertIsNone(rows[0].error_kcal)

    def test_computes_ingested_and_tissue_surplus_and_their_error(self):
        logs = [FakeLog(BASE_DATE, 2400.0), FakeLog(BASE_DATE + timedelta(days=7), 2350.0)]
        results = [
            make_result(0, tdee=2400.0, fat_mass_kg=18.0, lean_mass_kg=72.0),
            make_result(1, tdee=2380.0, fat_mass_kg=18.1, lean_mass_kg=72.3),  # +0.1 fat, +0.3 lean
        ]
        ec = EngineConstants(kcal_per_kg_fat=7700.0, lean_tissue_kcal_per_kg=2100.0)
        rows = compute_energy_reconciliation(logs, results, ec)

        surplus_ingested = 2400.0 - 2400.0  # E_0 - TDEE_0
        surplus_tissue = (0.1 * 7700.0 + 0.3 * 2100.0) / 7
        self.assertAlmostEqual(rows[0].surplus_ingested_kcal, surplus_ingested, delta=1e-9)
        self.assertAlmostEqual(rows[0].surplus_tissue_kcal, surplus_tissue, delta=1e-9)
        self.assertAlmostEqual(
            rows[0].error_kcal, abs(surplus_ingested - surplus_tissue), delta=1e-9
        )

    def test_assumed_intake_week_has_no_ingested_surplus_or_error(self):
        logs = [
            FakeLog(BASE_DATE, 2400.0, intake_is_real=False),
            FakeLog(BASE_DATE + timedelta(days=7), 2350.0),
        ]
        results = [make_result(0), make_result(1)]
        rows = compute_energy_reconciliation(logs, results)
        self.assertIsNone(rows[0].surplus_ingested_kcal)
        self.assertIsNone(rows[0].error_kcal)
        # Tissue surplus doesn't depend on intake reality, so it's still computed.
        self.assertIsNotNone(rows[0].surplus_tissue_kcal)

    def test_rolling_mean_covers_only_the_configured_window(self):
        logs = [FakeLog(BASE_DATE + timedelta(days=7 * i), 2400.0) for i in range(5)]
        results = [make_result(i, tdee=2400.0) for i in range(5)]
        rows = compute_energy_reconciliation(logs, results, window_weeks=2)
        # Every week's error is 0 here (constant tdee, no mass change), so the
        # rolling mean of the last two computed errors should also be 0.
        self.assertEqual(rows[2].error_rolling_mean_kcal, 0.0)

    def test_sorts_out_of_order_input_by_date(self):
        logs = [
            FakeLog(BASE_DATE + timedelta(days=7), 2350.0),
            FakeLog(BASE_DATE, 2400.0),
        ]
        results = [make_result(1), make_result(0)]
        rows = compute_energy_reconciliation(logs, results)
        self.assertEqual([r.date for r in rows], sorted(r.date for r in rows))


if __name__ == "__main__":
    unittest.main()
