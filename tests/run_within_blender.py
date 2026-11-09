import json
import os
import platform
import sys
from pathlib import Path

import bpy
import pytest

print("-----------------------------------------------------")
print("Python version:", sys.version)
print("Python executable:", sys.executable)

print("Python paths:")
for p in sys.path:
    print(f" {p}")

user_dirs = ['BLENDER_USER_RESOURCES', 'BLENDER_USER_CONFIG', 'BLENDER_USER_SCRIPTS', 'XDG_CONFIG_HOME']
print("USER DIR:")
print('\n'.join(filter(None, [os.environ.get(var, '') for var in user_dirs])))
print("-----------------------------------------------------")

import sample_data

addons_path: Path = sample_data.sample_data_path.parent


class ReportCollector:
    """Counts per-outcome test totals for the JSON summary."""

    def __init__(self) -> None:
        self.tests = 0
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.skipped = 0

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when == "setup":
            if report.outcome == "failed":  # Error before the test body could run
                self.tests += 1
                self.errors += 1
            elif report.outcome == "skipped":  # pytest-style skips are reported in the setup phase
                self.tests += 1
                self.skipped += 1
        elif report.when == "call":
            self.tests += 1
            if report.outcome == "passed":
                self.passed += 1
            elif report.outcome == "skipped":  # Unittest-based skips are reported in the call phase
                self.skipped += 1
            else:
                self.failed += 1


collector = ReportCollector()
pytest.main([str(addons_path), "-v", "--tb=short", "-p", "no:cacheprovider"], plugins=[collector])

report = {
    "blender_version": bpy.app.version_string,
    "system": platform.system(),
    "total_tests": collector.tests,
    "total_passed": collector.passed,
    "total_failed": collector.failed,
    "total_errors": collector.errors,
    "total_skipped": collector.skipped,
}

env_log_file_path = os.getenv('TEST_RESULTS_PATH')
log_file_path = Path(env_log_file_path) if env_log_file_path else addons_path / 'test_results.json'

with open(log_file_path, 'w') as log_file:
    json.dump(report, log_file, indent=4)

print(f"Test summary is saved to {log_file_path}")
