"""แปลง contract เป็น JSON Schema — เผื่อวันหนึ่งเขียน agent ด้วยภาษาอื่น
สัญญาจริงคือ JSON Schema ไม่ใช่ Python  ->  py export_schema.py out/
"""
import json
import sys
from pathlib import Path

from . import agents as A

PAIRS = [
    ("strategist", A.StrategistInput, A.StrategistOutput),
    ("writer", A.WriterInput, A.WriterOutput),
    ("reach_guard", A.GuardInput, A.GuardOutput),
    ("concierge", A.ConciergeInput, A.ConciergeOutput),
    ("scorer", A.ScorerInput, A.ScorerOutput),
    ("closer", A.CloserInput, A.CloserOutput),
    ("analyst", A.AnalystInput, A.AnalystOutput),
]


def main(out_dir: str = "schema_json") -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, inp, outp in PAIRS:
        for suffix, model in (("in", inp), ("out", outp)):
            path = out / f"{name}.{suffix}.json"
            path.write_text(
                json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  {path}")


if __name__ == "__main__":
    main(*sys.argv[1:])
