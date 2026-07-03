import unittest
from datetime import date

from server.src.services.composition import Anthropometry


class AnthropometryTest(unittest.TestCase):
    def test_compute_age_floors_to_whole_years(self):
        age = Anthropometry.compute_age(date(2026, 6, 26), date(2001, 8, 22))
        self.assertEqual(age, 24)

    def test_compute_age_rejects_as_of_before_birthdate(self):
        with self.assertRaises(ValueError):
            Anthropometry.compute_age(date(2000, 1, 1), date(2001, 8, 22))

    def test_compute_bmi(self):
        self.assertAlmostEqual(Anthropometry.compute_bmi(90.7, 176), 29.28, delta=0.01)

    def test_compute_bmi_rejects_non_positive(self):
        with self.assertRaises(ValueError):
            Anthropometry.compute_bmi(0, 176)

    def test_compute_ffmi_and_adjusted(self):
        ffmi = Anthropometry.compute_ffmi(72.64, 176)
        self.assertAlmostEqual(ffmi, 23.45, delta=0.01)
        ffmi_adj = Anthropometry.compute_ffmi_adjusted(ffmi, 176)
        self.assertAlmostEqual(ffmi_adj, 23.70, delta=0.01)

    def test_compute_ffmi_adjusted_with_custom_coef(self):
        ffmi = Anthropometry.compute_ffmi(72.64, 176)
        ffmi_adj = Anthropometry.compute_ffmi_adjusted(ffmi, 176, ffmi_coef=6.1)
        self.assertAlmostEqual(ffmi_adj, ffmi + 6.1 * (1.80 - 1.76), delta=0.001)


if __name__ == "__main__":
    unittest.main()
