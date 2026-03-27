import os
import tempfile
import unittest

from fastapi.testclient import TestClient

import app as app_module


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_activities.sqlite")
        os.environ["DATABASE_PATH"] = self.db_path

    def tearDown(self):
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def test_signup_persists_across_restart(self):
        email = "persistence-check@mergington.edu"

        with TestClient(app_module.app) as client:
            signup_response = client.post(
                "/activities/Chess Club/signup",
                params={"email": email},
            )
            self.assertEqual(signup_response.status_code, 200)

        with TestClient(app_module.app) as client:
            activities = client.get("/activities").json()

        self.assertIn(email, activities["Chess Club"]["participants"])

    def test_duplicate_registration_is_rejected(self):
        email = "duplicate-check@mergington.edu"

        with TestClient(app_module.app) as client:
            first = client.post(
                "/activities/Programming Class/signup",
                params={"email": email},
            )
            second = client.post(
                "/activities/Programming Class/signup",
                params={"email": email},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json()["detail"], "Student is already signed up")


if __name__ == "__main__":
    unittest.main()