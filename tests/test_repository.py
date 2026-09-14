import unittest
from pathlib import Path

from check_repository import inspect


class RepositoryChecks(unittest.TestCase):
    def test_clean_source(self):
        self.assertEqual(inspect(Path("src/a.py"), b"x=1\n"), [])

    def test_syntax_error(self):
        self.assertTrue(inspect(Path("src/a.py"), b"def :"))

    def test_raw_data_blocked(self):
        self.assertTrue(inspect(Path("data/raw/field.csv"), b"a,b"))

    def test_raw_readme_allowed(self):
        self.assertEqual(inspect(Path("data/raw/README.md"), b"policy"), [])

    def test_secret_pattern(self):
        fake = ("AK" + "IA" + "A" * 16).encode()
        self.assertTrue(inspect(Path("settings.txt"), fake))

    def test_notebook_output_blocked(self):
        data = b'{"cells":[{"cell_type":"code","outputs":[{"text":"x"}],"execution_count":1}]}'
        self.assertTrue(inspect(Path("example.ipynb"), data))

    def test_large_file_blocked(self):
        self.assertTrue(inspect(Path("x.bin"), b"x" * (5 * 1024 * 1024 + 1)))

    def test_credential_filename(self):
        self.assertTrue(inspect(Path(".env"), b"example"))
