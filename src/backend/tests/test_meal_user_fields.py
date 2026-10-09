import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routes import build_meal_fields


class MealUserFieldTests(unittest.TestCase):
    def test_single_person_meal_does_not_copy_to_other_person(self):
        payload = build_meal_fields(
            {
                "description": "Pasta al pesto",
                "annalisa": "Pasta al pesto",
            }
        )

        self.assertIsNone(payload["antonio"])
        self.assertEqual(payload["annalisa"], "Pasta al pesto")
        self.assertEqual(payload["description"], "Pasta al pesto")


if __name__ == "__main__":
    unittest.main()
