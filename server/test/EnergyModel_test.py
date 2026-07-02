import unittest

from server.src.services.composition import EnergyModel


class EnergyModelTest(unittest.TestCase):
    def test_compute_bmr(self):
        self.assertAlmostEqual(EnergyModel.compute_bmr(72.64), 2098.08, delta=0.01)

    def test_compute_neat(self):
        self.assertAlmostEqual(EnergyModel.compute_neat(90.7, 5000), 226.75, delta=0.01)

    def test_compute_tdee(self):
        self.assertAlmostEqual(
            EnergyModel.compute_tdee(2098.08, 226.75), 2583.14, delta=0.01
        )

    def test_compute_target_calories(self):
        self.assertAlmostEqual(
            EnergyModel.compute_target_calories(2098.08, 226.75, 500.5),
            2027.03,
            delta=0.01,
        )

    def test_compute_intake_diff(self):
        self.assertAlmostEqual(
            EnergyModel.compute_intake_diff(2014.30, 2027.03), -12.73, delta=0.01
        )


if __name__ == "__main__":
    unittest.main()
