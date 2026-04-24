from __future__ import annotations

import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "npide.db"

IMPROVING_RATIOS = [0.52, 0.57, 0.63, 0.69, 0.75, 0.82]
STABLE_RATIOS = [0.67, 0.68, 0.67, 0.69, 0.68, 0.67]
WORSENING_RATIOS = [0.79, 0.74, 0.69, 0.64, 0.59, 0.54]


def build_ratio_series(kind: str, district_index: int) -> list[float]:
    if kind == "improving":
        base = IMPROVING_RATIOS
    elif kind == "stable":
        base = STABLE_RATIOS
    else:
        base = WORSENING_RATIOS

    # Add a tiny deterministic offset so districts do not share identical rows.
    offset = ((district_index % 5) - 2) * 0.01
    return [min(0.92, max(0.35, ratio + offset)) for ratio in base]


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    districts = [row[0] for row in cur.execute(
        "SELECT DISTINCT district FROM district_monthly ORDER BY district"
    )]

    for index, district in enumerate(districts):
        kind = ("improving", "stable", "worsening")[index % 3]
        ratios = build_ratio_series(kind, index)

        rows = cur.execute(
            "SELECT id, month, expected FROM district_monthly WHERE district = ? ORDER BY month",
            (district,),
        ).fetchall()

        for row_index, (record_id, month, expected) in enumerate(rows):
            ratio = ratios[row_index]
            actual = int(round(expected * ratio))
            cur.execute(
                "UPDATE district_monthly SET actual = ? WHERE id = ?",
                (actual, record_id),
            )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
