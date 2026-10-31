import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from generator_v2 import generate_all
from validator import validate_data


def test_reproducible_generation():
    with TemporaryDirectory() as temp_dir:
        first_dir = Path(temp_dir) / "first"
        second_dir = Path(temp_dir) / "second"
        generate_all(first_dir, scale="starter")
        generate_all(second_dir, scale="starter")

        first_files = sorted(path.name for path in first_dir.iterdir())
        second_files = sorted(path.name for path in second_dir.iterdir())
        assert first_files == second_files

        for filename in first_files:
            assert (first_dir / filename).read_bytes() == (second_dir / filename).read_bytes()


def test_validation_accepts_generated_dataset():
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        generate_all(root, scale="starter")
        issues = validate_data(root)
        assert issues == []


def test_full_scale_generation_has_expected_file_set():
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        datasets = generate_all(root, scale="full")
        csv_files = sorted(path.name for path in root.glob("*.csv"))
        assert "students.csv" in csv_files
        assert "invoices.csv" in csv_files
        assert "scholarships.csv" in csv_files
        assert "payments.csv" in csv_files
        assert "ground_truth.csv" in csv_files
        assert "student_balances.csv" in csv_files
        assert len(datasets["students"]) == 10_000
        assert len(datasets["programs"]) == 20
        assert len(datasets["invoices"]) == 30_000
        assert len(datasets["scholarships"]) == 15_000
        assert len(datasets["payments"]) == 50_000


def test_generated_json_exports_exist():
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        generate_all(root, scale="starter")
        json_files = sorted(path.name for path in root.glob("*.json"))
        assert "students.json" in json_files
        assert "ground_truth.json" in json_files
        assert "student_balances.json" in json_files
        assert "anomaly_cases.json" in json_files


def test_all_required_anomalies_are_detected_without_corrupting_baseline():
    required_types = {
        "PAYMENT_ALLOCATION_EXCEEDS_PAYMENT",
        "SCHOLARSHIP_EXCEEDS_ELIGIBLE_FEES",
        "DUPLICATE_INVOICE_GENERATION",
        "REFUND_EXCEEDS_NET_PAID",
        "BALANCE_DISAGREES_WITH_LEDGER",
    }
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        generate_all(root, scale="starter")
        cases = pd.read_csv(root / "anomaly_cases.csv")
        assert set(cases["issue_type"]) == required_types
        assert validate_data(root) == []


def test_sql_seed_import_matches_csv_row_counts():
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        datasets = generate_all(root, scale="starter")
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript((root / "seed_data.sql").read_text(encoding="utf-8"))
            for name, frame in datasets.items():
                count = connection.execute(
                    f'SELECT COUNT(*) FROM "{name}"'
                ).fetchone()[0]
                assert count == len(frame)
                assert pd.read_csv(root / f"{name}.csv").equals(frame)
                assert json.loads((root / f"{name}.json").read_text(encoding="utf-8")) == (
                    json.loads(frame.to_json(orient="records"))
                )
                sql_frame = pd.read_sql_query(f'SELECT * FROM "{name}"', connection)
                assert sql_frame.equals(frame)
        finally:
            connection.close()
