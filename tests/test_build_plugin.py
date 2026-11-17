import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.build_plugin import PLUGIN_DIRECTORY, build_plugin_zip


class TestBuildPlugin(unittest.TestCase):
    def test_builds_installable_plugin_root_and_excludes_development_files(self):
        repository = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "HazardMapGame_tool.zip"
            build_plugin_zip(repository, output)

            with ZipFile(output) as archive:
                names = set(archive.namelist())

        self.assertIn(f"{PLUGIN_DIRECTORY}/metadata.txt", names)
        self.assertIn(f"{PLUGIN_DIRECTORY}/__init__.py", names)
        self.assertIn(f"{PLUGIN_DIRECTORY}/hmg_utils.py", names)
        self.assertNotIn(f"{PLUGIN_DIRECTORY}/utils.py", names)
        self.assertIn(f"{PLUGIN_DIRECTORY}/ui/main_window.ui", names)
        self.assertFalse(any("/__pycache__/" in name for name in names))
        self.assertFalse(any(name.endswith(".pyc") for name in names))
        self.assertFalse(
            any(name.startswith(f"{PLUGIN_DIRECTORY}/tests/") for name in names)
        )
        self.assertFalse(
            any(name.startswith(f"{PLUGIN_DIRECTORY}/doc/") for name in names)
        )


if __name__ == "__main__":
    unittest.main()
