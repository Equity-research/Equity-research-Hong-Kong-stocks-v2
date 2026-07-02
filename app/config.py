from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
DB_PATH = DATA_DIR / "hk_ipo.db"


def load_rules() -> dict:
    with (ROOT / "scoring_rules.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)

