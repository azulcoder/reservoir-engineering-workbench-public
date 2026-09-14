import json
import tempfile
import unittest
from pathlib import Path

from run_demo import run


class WorkflowTests(unittest.TestCase):
    def test_demo_gates_and_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            result = run(Path(d))
            self.assertTrue(result["passes_demo_gates"])
            manifest = json.loads((Path(d) / "run_manifest.json").read_text())
            self.assertEqual(len(manifest["config_sha256"]), 64)
            self.assertEqual(result["training_observations"], 9)
            self.assertEqual(result["holdout_observations"], 4)

    def test_numerical_outputs_repeat(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            ra, rb = run(Path(a)), run(Path(b))
            self.assertEqual(ra, rb)
            self.assertEqual(
                (Path(a) / "observations.csv").read_bytes(),
                (Path(b) / "observations.csv").read_bytes(),
            )

    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            (path / "important.txt").write_text("preserve")
            with self.assertRaises(ValueError):
                run(path)
            self.assertEqual((path / "important.txt").read_text(), "preserve")
