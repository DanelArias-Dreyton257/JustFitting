import unittest

from server.src.services.composition import EnergyModel


class EnergyModelTest(unittest.TestCase):
    def test_compute_bmr(self):
        self.assertAlmostEqual(EnergyModel.compute_bmr(72.64), 2098.08, delta=0.01)

    def test_compute_bmr_mifflin_male(self):
        # 10*90.7 + 6.25*176 - 5*24 + 5
        self.assertAlmostEqual(
            EnergyModel.compute_bmr_mifflin(90.7, 176, 24, sex=1), 1892.0, delta=0.01
        )

    def test_compute_bmr_mifflin_female(self):
        # 10*90.7 + 6.25*176 - 5*24 - 161
        self.assertAlmostEqual(
            EnergyModel.compute_bmr_mifflin(90.7, 176, 24, sex=0), 1726.0, delta=0.01
        )

    def test_compute_neat(self):
        self.assertAlmostEqual(EnergyModel.compute_neat(90.7, 5000), 226.75, delta=0.01)

    def test_compute_tdee(self):
        self.assertAlmostEqual(
            EnergyModel.compute_tdee(2098.08, 226.75), 2583.14, delta=0.01
        )

    def test_compute_tdee_with_cardio_eat_term(self):
        # (bmr + neat + eat) / (1 - tef); eat=0 reproduces the base case.
        base = EnergyModel.compute_tdee(2098.08, 226.75, eat=0.0)
        with_cardio = EnergyModel.compute_tdee(2098.08, 226.75, eat=300.0)
        self.assertAlmostEqual(base, 2583.14, delta=0.01)
        self.assertAlmostEqual(with_cardio, base + 300.0 / (1 - 0.10), delta=0.01)

    def test_compute_target_calories(self):
        self.assertAlmostEqual(
            EnergyModel.compute_target_calories(2098.08, 226.75, 500.5),
            2027.03,
            delta=0.01,
        )

    def test_compute_target_calories_with_cardio_eat_term(self):
        base = EnergyModel.compute_target_calories(2098.08, 226.75, 500.5, eat=0.0)
        with_cardio = EnergyModel.compute_target_calories(2098.08, 226.75, 500.5, eat=300.0)
        self.assertAlmostEqual(with_cardio, base + 300.0 / (1 - 0.10), delta=0.01)

    def test_compute_intake_diff(self):
        self.assertAlmostEqual(
            EnergyModel.compute_intake_diff(2014.30, 2027.03), -12.73, delta=0.01
        )


if __name__ == "__main__":
    unittest.main()
