from pathlib import Path
from tempfile import TemporaryDirectory
from django.conf import settings
from django.db import connections
from django.test.runner import DiscoverRunner


class FileDatabaseRunner(DiscoverRunner):
    def build_suite(self, test_labels=None, **kwargs):
        # manage.py may be invoked from the repository root, outside this app.
        labels = ([str(Path(__file__).resolve().parent)]
                  if not test_labels or list(test_labels) in (["."], ["tests"])
                  else test_labels)
        return super().build_suite(labels, **kwargs)

    def setup_databases(self, **kwargs):
        self.directory = TemporaryDirectory(prefix="workpal-test-")
        self.original_name = connections['default'].settings_dict['TEST'].get('NAME')
        self.original_database_name = connections['default'].settings_dict['NAME']
        connections['default'].settings_dict['TEST']['NAME'] = str(Path(self.directory.name) / 'test.sqlite3')
        try:
            return super().setup_databases(**kwargs)
        except BaseException:
            self.cleanup()
            raise

    def cleanup(self):
        connections.close_all()
        connections['default'].settings_dict['NAME'] = self.original_database_name
        connections['default'].settings_dict['TEST']['NAME'] = self.original_name
        self.directory.cleanup()

    def teardown_databases(self, old_config, **kwargs):
        try:
            super().teardown_databases(old_config, **kwargs)
        finally:
            self.cleanup()

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, 'testserver']
