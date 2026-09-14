# Executed synthetic example

This directory preserves one locally executed verification demonstration. Start with [report.md](report.md), then inspect the [observations](observations.csv), [numerical summary](summary.json), and [run manifest](run_manifest.json).

The data are synthetic. The purpose is to verify a narrow volumetric-gas workflow with explicit provenance, not to establish real-field performance. Re-run with a new empty output directory using `python scripts/run_demo.py --out artifacts/another-run`.

Numerical CSV and summary outputs are expected to reproduce under the documented environment. Runtime timestamps, platform strings and Git metadata may differ; those differences are intentional provenance, not numerical regressions.
