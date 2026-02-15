from datetime import date
from pathlib import Path

import pandas as pd


def main() -> None:
    frame = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
    if "Symbol" not in frame.columns:
        raise RuntimeError("Symbol column was not found in Wikipedia table")

    tickers = sorted(set(frame["Symbol"].astype(str).str.upper().str.replace(".", "-", regex=False)))

    out = pd.DataFrame({"ticker": tickers, "as_of": [date.today().isoformat()] * len(tickers)})
    path = Path(__file__).resolve().parent.parent / "app" / "data" / "sp500_snapshot_feb2026.csv"
    out.to_csv(path, index=False)

    print(f"Wrote {len(tickers)} tickers to {path}")


if __name__ == "__main__":
    main()
