import importlib
import inspect
import json
import os
import platform
import sys
from typing import Any
import unittest
from pathlib import Path
import bpy
import sys

print("-----------------------------------------------------")
print("Python version:", sys.version)
print("Python executable:", sys.executable)

for p in sys.path:
    print(f" {p}")


print(f"User dir: {os.environ['BLENDER_USER_RESOURCES']}")
print("-----------------------------------------------------")
import sample_data

for p in sys.path:
    print(p)

for p in sys.path:
    print(p, file=sys.stderr)

# sample_project.SampleProject.blender_as_module = False


# def pytest_configure(config) -> None:
#     config.option.log_cli = True
#     config.option.log_cli_level = "DEBUG"


addons_path: Path = sample_data.sample_data_path.parent

# For some reason default value is:
# blender/4.2/scripts/       rhubarb_lipsync/bin/rhubarb`
# blender/4.2/scripts/addons/rhubarb_lipsync/bin/
#
# print('!!!!!')
# print(bpy.utils.user_resource('SCRIPTS', path="addons"))
# prefs: Path = RhubarbAddonPreferences.from_context(bpy.context)
# print(prefs.executable_path_string)
# addons/rhubarb_lipsync/bin/


# Discover all test modules in the addons_path
def discover_test_modules(path: Path):
    test_modules = []
    for file in path.rglob('test_*.py'):
        # Convert file path to module name
        module_name = str(file.relative_to(path)).replace('/', '.').replace('\\', '.').replace('.py', '')
        test_modules.append(module_name)
    return test_modules


test_modules = discover_test_modules(addons_path)

# test_modules = [
#     'test_ui_utils',
#     'test_baking_preparation',
#     'test_process_sound_file',
# ]
print(f"Discovered test modules: {test_modules}")


def load_tests_from_module(module_name) -> unittest.TestSuite:
    module = importlib.import_module(module_name)
    suite = unittest.TestSuite()
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and issubclass(obj, unittest.TestCase):
            suite.addTests(unittest.TestLoader().loadTestsFromTestCase(obj))
    return suite


# Discover and load all tests from the specified modules
all_tests = unittest.TestSuite()
for module_name in test_modules:
    all_tests.addTests(load_tests_from_module(module_name))

print(f"Running tests {all_tests}")


def create_test_report(result) -> dict[str, Any]:
    report = {
        "blender_version": bpy.app.version_string,
        "system": platform.system(),
        "total_tests": result.testsRun,
        "total_passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        "total_failed": len(result.failures),
        "total_errors": len(result.errors),
        "total_skipped": len(result.skipped),
    }
    return report


runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(all_tests)
print("Done")


env_log_file_path = os.getenv('TEST_RESULTS_PATH')
default_log_file_path = Path(addons_path / 'test_results.json')

log_file_path = Path(env_log_file_path) if env_log_file_path else default_log_file_path

with open(log_file_path, 'w') as log_file:
    # Create and write JSON report
    report = create_test_report(result)
    json.dump(report, log_file, indent=4)

print(f"Test summary is saved to {log_file_path}")
