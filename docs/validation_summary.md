# Validation Summary

## Verified run

Full mode was generated with:

```powershell
python generator_v2.py --mode full --output-dir output/full
python validator.py --data-dir output/full
```

The first observed full generation took **10.99 seconds**; refreshing the same default `data/` output took **9.49 seconds**. Validation completed in **3.50 seconds** for `output/full` and **2.94 seconds** for `data/`, with no errors and all **5 of 5** required anomaly scenarios detected. Each full dataset contained **299,052 total rows** across the 14 exported datasets.

| Dataset | Rows |
| --- | ---: |
| Students | 10,000 |
| Programs | 20 |
| Fee schedules | 60 |
| Enrollments | 30,000 |
| Invoices | 30,000 |
| Invoice lines | 90,000 |
| Eligibility | 10,000 |
| Scholarships | 15,000 |
| Payments | 50,000 |
| Payment allocations | 50,000 |
| Refunds | 1,488 |
| Student balances | 10,000 |
| Anomaly cases | 5 |
| Ground truth | 2,479 |

CSV, JSON, and SQLite SQL export row counts matched for every dataset. The SQL seed was executed in an in-memory SQLite database. Starter-mode CLI generation took **0.75 seconds**, and starter validation completed in **1.25 seconds**.

## Automated checks

- `python -m py_compile generator.py generator_v2.py validator.py test_run.py tests\test_generator.py` — passed.
- `python -m pytest -q` — **6 passed** in 24.75 seconds, including the full-volume generation test.
- `python test_run.py` — passed; generated files were byte-identical across two starter runs and the data validated.
- Pylance workspace diagnostics — no issues.

Peak memory usage was not measured. No machine-specific runtime limit is claimed.

## Scope notes

Intentional anomalies are scenario values kept separate from baseline data so the baseline still passes relationship and ledger checks. Late-fee policy, fee-waiver transactions, explicit cancellation/withdrawal events, and event-sourced history remain outside the current model because their business rules are unspecified.
