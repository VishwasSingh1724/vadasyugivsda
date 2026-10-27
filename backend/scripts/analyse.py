"""Print the January headline findings used in the pitch.  Usage: python -m scripts.analyse"""

from app.core.config import get_settings
from app.domain import metrics as m
from app.repository import CsvRepository
from app.services.analytics import AnalyticsService


def main() -> None:
    s = AnalyticsService(CsvRepository(get_settings().data_dir), get_settings())
    d = s.decision_errors(None, None)
    h = m.summarize(d)
    debiased = float((d["error_mw"] - d["error_mw"].mean()).abs().mean())
    print(f"Hours scored: {h.n}  coverage: {s.coverage_pct(None, None):.1f}%")
    print(
        f"MAE {h.mae_mw:.0f} MW ({h.nmae_pct:.1f}% of mean wind)  RMSE {h.rmse_mw:.0f}  P90 {h.p90_abs_mw:.0f}"
    )
    print(
        f"Bias {h.bias_mw:+.0f} MW -> {abs(h.bias_mw) / h.mae_mw:.0%} of MAE; bias-corrected MAE {debiased:.0f} MW"
    )
    v = s.vintage_errors(None, None)
    for k, x in m.grouped(v, m.horizon_bucket(v["horizon_h"])):
        print(
            f"  horizon {k:>7}: MAE {x.mae_mw:6.0f}  bias {x.bias_mw:+6.0f}  nMAE {x.nmae_pct:4.1f}%"
        )
    worst = sorted(m.grouped(d, d["delivery_date"]), key=lambda kv: -kv[1].mae_mw)[:3]
    print("Worst days:", [(k, round(x.mae_mw)) for k, x in worst])


if __name__ == "__main__":
    main()
