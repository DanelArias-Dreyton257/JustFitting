import unittest

from server.src.services.composition import BodyFat


class BodyFatTest(unittest.TestCase):
    def test_compute_rfm(self):
        self.assertAlmostEqual(BodyFat.compute_rfm(176, 80.0), 0.2000, delta=0.001)

    def test_compute_navy(self):
        self.assertAlmostEqual(
            BodyFat.compute_navy(176, 80.0, 35.0), 0.1519, delta=0.001
        )

    def test_compute_navy_requires_waist_greater_than_neck(self):
        with self.assertRaises(ValueError):
            BodyFat.compute_navy(176, 35.0, 35.0)
        with self.assertRaises(ValueError):
            BodyFat.compute_navy(176, 30.0, 35.0)

    def test_compute_deurenberg(self):
        self.assertAlmostEqual(
            BodyFat.compute_deurenberg(29.28, 24, sex=1), 0.2446, delta=0.001
        )

    def test_compute_body_fat_is_weighted_mean(self):
        bf = BodyFat.compute_body_fat(rfm=0.20, navy=0.10, deurenberg=0.30)
        self.assertAlmostEqual(bf, 0.5 * 0.20 + 0.25 * 0.10 + 0.25 * 0.30)

    def test_fat_and_lean_mass_sum_to_weight(self):
        weight_kg = 90.7
        body_fat = 0.1991
        fat_mass = BodyFat.compute_fat_mass(weight_kg, body_fat)
        lean_mass = BodyFat.compute_lean_mass(weight_kg, body_fat)
        self.assertAlmostEqual(fat_mass + lean_mass, weight_kg, delta=0.01)

    def test_compute_above_target(self):
        self.assertAlmostEqual(
            BodyFat.compute_above_target(0.1991, 0.15), 0.0491, delta=0.001
        )


if __name__ == "__main__":
    unittest.main()
