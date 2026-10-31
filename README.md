# YottaFlex Tuition and Fee Management Dataset

A deterministic Python generator for synthetic academic billing data. It creates relational CSV and JSON files, a SQLite-compatible SQL seed, a source manifest, and separately labelled anomaly examples. No production or personal data is used.

## Requirements

- Python 3.10 or newer
- Dependencies from `requirements.txt`

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Generate datasets

```powershell
python generator_v2.py --mode starter --output-dir output/starter
python generator_v2.py --mode full --output-dir output/full
```

The starter mode uses 1,000 students, 5 programs, and one term. Full mode is fixed to the assignment volumes and refuses smaller overrides:

| Entity | Full rows |
| --- | ---: |
| Students | 10,000 |
| Programs | 20 |
| Fee schedules | 60 |
| Enrollments | 30,000 |
| Invoices | 30,000 |
| Invoice lines | 90,000 |
| Scholarships | 15,000 |
| Payments | 50,000 |
| Payment allocations | 50,000 |

Both modes use the same generator functions and default random seed (`20261022`). Each run prints progress for ten generation/export stages, record counts, per-stage elapsed time, total time, and the destination folder. Use `--seed` to intentionally select another seed.

Generated datasets are written as CSV and JSON, with `seed_data.sql` and `source_manifest.json`. The `student_balances` table is included in all three exports. The seed contains typed columns and primary-key constraints and can be loaded by SQLite.

## Validate and test

```powershell
python validator.py --data-dir output/starter
python -m pytest -q
python test_run.py
```

The validator checks required files and columns, primary/foreign keys, duplicate invoices, allowed values, dates, eligibility, scholarship caps, invoice lines, payment allocations, refunds, invoice status, and student balance reconciliation. It also checks the five labelled anomaly examples. The test suite includes a full-mode exact-volume run, starter validation, export checks, and byte-for-byte reproducibility.

`test_run.py` performs reproducibility checks in starter mode so it remains quick:

```powershell
python test_run.py
```

## Data model and anomaly handling

The baseline tables model students, programs, term fee schedules, enrollments, invoices and invoice lines, eligibility, scholarships, payments, allocations, refunds, and student balances. `ground_truth` contains labelled issue records. `anomaly_cases` stores five deliberately anomalous *scenario values* separately from the clean baseline ledgers:

1. Payment allocation greater than its payment.
2. Scholarship greater than the related invoice fees.
3. Duplicate invoice generation for an enrollment.
4. Refund greater than net allocated payment.
5. Student balance different from the ledger-derived balance.

This separation preserves baseline financial reconciliation while providing testable, labelled anomaly evidence. See [docs/schema.md](docs/schema.md), [docs/data_dictionary.md](docs/data_dictionary.md), and [docs/validation_summary.md](docs/validation_summary.md) for relationships, field definitions, assumptions, and verified results.

## Repository layout

```text
.
├── data/                 # Canonical generated datasets
├── docs/                 # Schema, dictionary, coverage, validation summary
├── tests/                # Automated tests
├── generator.py          # CLI compatibility entry point
├── generator_v2.py       # Generator implementation and CLI
├── validator.py          # Dataset validation CLI
├── test_run.py           # Starter reproducibility check
├── requirements.txt
└── README.md
```

## Scope and limitations

All records are synthetic. Financial calculations use integer currency units and fixed example dates. The model currently does not implement late-fee policies, fee-waiver transactions, explicit withdrawal/cancellation events, or event-sourced history; those rules require assignment-specific rates and lifecycle semantics that are not defined in the available project data.
