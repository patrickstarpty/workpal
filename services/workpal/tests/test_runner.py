from pathlib import Path
from unittest.mock import patch

from django.db import connections
from django.test import SimpleTestCase
from django.test.runner import DiscoverRunner

from tests.runner import FileDatabaseRunner


class RunnerTests(SimpleTestCase):
    def test_default_command_discovers_service_tests(self):
        for labels in (None, ["."]):
            suite = FileDatabaseRunner(verbosity=0).build_suite(labels)
            self.assertGreater(suite.countTestCases(), 0)

    def test_setup_failure_removes_directory_and_restores_database_names(self):
        config = connections["default"].settings_dict
        original_name = config["NAME"]
        original_test_name = config["TEST"]["NAME"]
        allocated = []
        runner = FileDatabaseRunner(verbosity=0)

        def failed_setup(**kwargs):
            allocated.append(Path(config["TEST"]["NAME"]))
            config["NAME"] = config["TEST"]["NAME"]
            raise RuntimeError("Simulated migration failure")

        try:
            with patch.object(DiscoverRunner, "setup_databases", side_effect=failed_setup):
                with self.assertRaisesRegex(RuntimeError, "migration failure"):
                    runner.setup_databases()
            self.assertFalse(allocated[0].parent.exists())
            self.assertEqual(config["NAME"], original_name)
            self.assertEqual(config["TEST"]["NAME"], original_test_name)
        finally:
            config["NAME"] = original_name
            config["TEST"]["NAME"] = original_test_name
