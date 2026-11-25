# TriVerify Task Factory

Automated, triple-verified generation of Harbor feature-development tasks from a real
codebase (Innodata AI Hackathon · Track 1 · `pallets/click` @ 8.5.1). By Trinetra Soft.

Full documentation is being written; see `docs/` and `output/REPORT.md` after CI runs.

```bash
pip install -e . "harbor==0.25.*"
python -m triverify run --config configs/click.toml --provider replay
```
