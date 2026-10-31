import argparse
import json
import random
import time
from pathlib import Path

import pandas as pd


SEED = 20261022
TERM_ID = "TERM-2026-FALL"
DEFAULT_TERMS = ["TERM-2026-FALL", "TERM-2026-SPRING", "TERM-2026-SUMMER"]

DATASET_SCHEMES = {
    "starter": {
        "student_count": 1_000,
        "program_count": 5,
        "term_ids": [TERM_ID],
    },
    "full": {
        "student_count": 10_000,
        "program_count": 20,
        "term_ids": DEFAULT_TERMS,
    },
}


def resolve_dataset_config(scale="full", student_count=None, program_count=None, term_ids=None):
    if scale not in DATASET_SCHEMES:
        raise ValueError(f"Unknown dataset mode {scale!r}; choose 'starter' or 'full'.")
    config = DATASET_SCHEMES[scale].copy()
    if student_count is not None:
        config["student_count"] = int(student_count)
    if program_count is not None:
        config["program_count"] = int(program_count)
    if term_ids is not None:
        config["term_ids"] = list(term_ids)
    return config


def generate_students(rng, student_count=10_000, force_active=False):
    return pd.DataFrame([
        {
            "student_id": f"STU-{student_number:06d}",
            "student_name": f"Student_{student_number}",
            "status": "ACTIVE" if force_active else rng.choices(
                ["ACTIVE", "INACTIVE"], weights=[9, 1]
            )[0],
        }
        for student_number in range(1, student_count + 1)
    ])


def generate_programs(rng, program_count=20):
    return pd.DataFrame([
        {
            "program_id": f"PRG-{program_number:03d}",
            "program_name": f"Program_{program_number}",
            "duration_years": rng.choice([2, 3, 4]),
            "tuition_fee": rng.randint(30_000, 150_000),
        }
        for program_number in range(1, program_count + 1)
    ])


def generate_fee_schedules(programs, rng, term_ids=None):
    term_ids = list(term_ids or [TERM_ID])
    schedules = []
    for _, program in programs.iterrows():
        for term_id in term_ids:
            schedules.append({
                "fee_schedule_id": f"FEE-{program['program_id'].split('-')[1]}-{term_id}",
                "program_id": program["program_id"],
                "term_id": term_id,
                "tuition_fee": int(program["tuition_fee"]),
                "lab_fee": rng.randint(1_000, 5_000),
                "exam_fee": rng.randint(500, 3_000),
            })
    return pd.DataFrame(schedules)


def generate_enrollments(students, programs, rng, term_ids=None, full_dataset=False):
    term_ids = list(term_ids or [TERM_ID])
    program_ids = programs["program_id"].tolist()
    enrollments = []
    for term_id in term_ids:
        for student_id in students.loc[
            students["status"] == "ACTIVE", "student_id"
        ]:
            status_value = "ACTIVE" if full_dataset else rng.choices(["ACTIVE", "WITHDRAWN"], weights=[9, 1])[0]
            enrollments.append({
                "enrollment_id": f"ENR-{len(enrollments) + 1:06d}",
                "student_id": student_id,
                "program_id": rng.choice(program_ids),
                "term_id": term_id,
                "status": status_value,
            })
    return pd.DataFrame(enrollments)


def generate_eligibility(students, rng, full_dataset=False):
    eligibility = []
    for student_number, student_id in enumerate(students["student_id"], start=1):
        if full_dataset:
            gpa = round(rng.uniform(7.5, 9.8), 2)
            family_income = rng.randint(50_000, 320_000)
        else:
            gpa = round(rng.uniform(5.0, 10.0), 2)
            family_income = rng.randint(50_000, 800_000)
        eligibility.append({
            "eligibility_id": f"ELG-{student_number:06d}",
            "student_id": student_id,
            "gpa": gpa,
            "family_income": family_income,
            "eligible": "YES" if gpa >= 7.5 and family_income <= 400_000 else "NO",
        })
    return pd.DataFrame(eligibility)


def generate_invoices(enrollments, fee_schedules):
    schedules = fee_schedules.set_index(["program_id", "term_id"]).to_dict("index")
    invoices = []
    active_enrollments = enrollments.loc[
        enrollments["status"] == "ACTIVE"
    ].itertuples(index=False)
    for enrollment in active_enrollments:
        schedule = schedules[(enrollment.program_id, enrollment.term_id)]
        invoice_number = len(invoices) + 1
        invoices.append({
            "invoice_id": f"INV-2026-{invoice_number:06d}",
            "enrollment_id": enrollment.enrollment_id,
            "student_id": enrollment.student_id,
            "fee_schedule_id": schedule["fee_schedule_id"],
            "invoice_date": "2026-08-01",
            "due_date": "2026-09-01",
            "total_amount": int(schedule["tuition_fee"] + schedule["lab_fee"] + schedule["exam_fee"]),
            "status": "OPEN",
        })
    return pd.DataFrame(invoices)


def generate_invoice_lines(invoices, fee_schedules):
    schedule_fees = fee_schedules.set_index("fee_schedule_id")
    invoice_schedules = invoices[["invoice_id", "fee_schedule_id"]].merge(
        schedule_fees[["tuition_fee", "lab_fee", "exam_fee"]],
        left_on="fee_schedule_id",
        right_index=True,
        how="left",
        validate="many_to_one",
    )
    fee_types = [
        ("TUITION", "tuition_fee"),
        ("LAB", "lab_fee"),
        ("EXAM", "exam_fee"),
    ]
    lines = [
        {
            "line_id": f"LINE-{(invoice_index - 1) * len(fee_types) + fee_index:08d}",
            "invoice_id": invoice["invoice_id"],
            "fee_type": fee_type,
            "amount": int(invoice[amount_column]),
        }
        for invoice_index, invoice in enumerate(
            invoice_schedules.to_dict("records"), start=1
        )
        for fee_index, (fee_type, amount_column) in enumerate(fee_types, start=1)
    ]
    return pd.DataFrame(lines, columns=["line_id", "invoice_id", "fee_type", "amount"])


def generate_scholarships(enrollments, invoices, eligibility, rng, target_count=None):
    eligible_students = set(eligibility.loc[eligibility["eligible"] == "YES", "student_id"])
    valid_enrollment_ids = set(enrollments["enrollment_id"])
    candidate_invoices = invoices.loc[
        invoices["student_id"].isin(eligible_students)
        & invoices["enrollment_id"].isin(valid_enrollment_ids)
    ].to_dict("records")
    if target_count is not None and target_count > 0:
        candidate_invoices = rng.sample(candidate_invoices, k=min(len(candidate_invoices), target_count))
    scholarships = []
    for invoice in candidate_invoices:
        award_cap = min(20_000, int(invoice["total_amount"] * 0.5))
        if award_cap <= 0:
            continue
        award_amount = max(1_000, int(rng.randint(1_000, award_cap)))
        scholarships.append({
            "scholarship_id": f"SCH-2026-{len(scholarships) + 1:06d}",
            "student_id": invoice["student_id"],
            "enrollment_id": invoice["enrollment_id"],
            "invoice_id": invoice["invoice_id"],
            "award_amount": award_amount,
            "status": "APPROVED",
        })
    return pd.DataFrame(scholarships, columns=[
        "scholarship_id", "student_id", "enrollment_id", "invoice_id", "award_amount", "status"
    ])


def generate_payments(invoices, scholarships, rng, target_count=None):
    scholarship_by_invoice = scholarships.groupby("invoice_id")["award_amount"].sum().to_dict()
    payments = []
    allocations = []
    invoice_records = invoices.set_index("invoice_id").to_dict("index")
    remaining_due = {
        invoice_id: int(invoice["total_amount"] - scholarship_by_invoice.get(invoice_id, 0))
        for invoice_id, invoice in invoice_records.items()
    }
    candidate_invoice_ids = [
        invoice_id for invoice_id, amount_due in remaining_due.items() if amount_due > 0
    ]
    candidate_positions = {
        invoice_id: position
        for position, invoice_id in enumerate(candidate_invoice_ids)
    }
    issued = 0
    while target_count is None or issued < target_count:
        if not candidate_invoice_ids:
            break
        invoice_id = rng.choice(candidate_invoice_ids)
        invoice = invoice_records[invoice_id]
        amount_due = remaining_due[invoice_id]
        payment_amount = max(1, min(amount_due, rng.randint(1, max(1, min(amount_due, 10_000)))))
        overpayment = 0 if rng.random() >= 0.05 else rng.randint(1, max(1, amount_due // 20))
        total_cash = payment_amount + overpayment
        payment_id = f"PAY-2026-{issued + 1:06d}"
        payments.append({
            "payment_id": payment_id,
            "student_id": invoice["student_id"],
            "payment_date": "2026-08-15",
            "amount": total_cash,
            "payment_method": rng.choice(["UPI", "CARD", "BANK_TRANSFER"]),
        })
        allocations.append({
            "allocation_id": f"ALLOC-{len(allocations) + 1:08d}",
            "payment_id": payment_id,
            "invoice_id": invoice_id,
            "allocated_amount": payment_amount,
        })
        remaining_due[invoice_id] -= payment_amount
        if remaining_due[invoice_id] == 0:
            position = candidate_positions.pop(invoice_id)
            last_invoice_id = candidate_invoice_ids.pop()
            if position < len(candidate_invoice_ids):
                candidate_invoice_ids[position] = last_invoice_id
                candidate_positions[last_invoice_id] = position
        issued += 1
    return (
        pd.DataFrame(payments, columns=["payment_id", "student_id", "payment_date", "amount", "payment_method"]),
        pd.DataFrame(allocations, columns=["allocation_id", "payment_id", "invoice_id", "allocated_amount"]),
    )


def generate_refunds(payments, allocations, rng):
    payment_students = payments.set_index("payment_id")["student_id"].to_dict()
    refunds = []
    for allocation in allocations.itertuples(index=False):
        if rng.random() >= 0.03:
            continue
        allocated_amount = int(allocation.allocated_amount)
        refunds.append({
            "refund_id": f"REF-2026-{len(refunds) + 1:06d}",
            "student_id": payment_students[allocation.payment_id],
            "payment_id": allocation.payment_id,
            "refund_amount": rng.randint(1, max(1, allocated_amount // 2)),
            "reason": rng.choice(["WITHDRAWAL", "OVERPAYMENT", "FEE_ADJUSTMENT"]),
        })
    return pd.DataFrame(refunds, columns=["refund_id", "student_id", "payment_id", "refund_amount", "reason"])


def update_invoice_statuses(invoices, scholarships, allocations, refunds):
    scholarship_by_invoice = scholarships.groupby("invoice_id")["award_amount"].sum()
    paid_by_invoice = allocations.groupby("invoice_id")["allocated_amount"].sum()
    refund_allocations = refunds.merge(
        allocations[["payment_id", "invoice_id"]], on="payment_id", how="left"
    )
    refunded_by_invoice = refund_allocations.groupby("invoice_id")["refund_amount"].sum()

    updated = invoices.copy()
    applied = updated["invoice_id"].map(paid_by_invoice).fillna(0)
    refunded = updated["invoice_id"].map(refunded_by_invoice).fillna(0)
    scholarship = updated["invoice_id"].map(scholarship_by_invoice).fillna(0)
    outstanding = updated["total_amount"] - scholarship - applied + refunded
    updated["status"] = "OPEN"
    updated.loc[(applied - refunded) > 0, "status"] = "PARTIAL"
    updated.loc[outstanding <= 0, "status"] = "PAID"
    return updated


def build_student_balances(students, invoices, scholarships, payments, allocations, refunds):
    balances = students[["student_id"]].copy()
    student_allocations = allocations.merge(
        invoices[["invoice_id", "student_id"]], on="invoice_id", how="left"
    )
    totals = [
        (invoices, "total_amount", "invoice_total"),
        (scholarships.loc[scholarships["status"] == "APPROVED"], "award_amount", "scholarship_total"),
        (payments, "amount", "payment_total"),
        (student_allocations, "allocated_amount", "allocated_payment_total"),
        (refunds, "refund_amount", "refund_total"),
    ]
    for frame, amount_column, total_column in totals:
        grouped = frame.groupby("student_id", as_index=False)[amount_column].sum().rename(
            columns={amount_column: total_column}
        )
        balances = balances.merge(grouped, on="student_id", how="left")

    total_columns = [column for _, _, column in totals]
    balances[total_columns] = balances[total_columns].fillna(0).astype("int64")
    balances["final_balance"] = (
        balances["invoice_total"]
        - balances["scholarship_total"]
        - balances["payment_total"]
        + balances["refund_total"]
    )
    return balances


def generate_anomaly_cases(invoices, scholarships, payments, allocations, refunds, balances):
    refund_by_payment = refunds.groupby("payment_id")["refund_amount"].sum()
    invoice_by_id = invoices.set_index("invoice_id")

    payment = payments.iloc[0]
    allocation = allocations.loc[allocations["payment_id"] == payment["payment_id"]].iloc[0]
    scholarship = scholarships.iloc[0]
    scholarship_invoice = invoice_by_id.loc[scholarship["invoice_id"]]
    duplicate_invoice = invoices.iloc[0]
    refundable = allocations.assign(
        net_paid=allocations["allocated_amount"]
        - allocations["payment_id"].map(refund_by_payment).fillna(0)
    )
    refundable = refundable.loc[refundable["net_paid"] > 0].iloc[0]
    balance = balances.iloc[0]

    return pd.DataFrame([
        {
            "issue_id": "ANOM-001",
            "issue_type": "PAYMENT_ALLOCATION_EXCEEDS_PAYMENT",
            "entity_name": "payment_allocations",
            "record_id": payment["payment_id"],
            "related_record_id": allocation["allocation_id"],
            "source_value": int(payment["amount"]),
            "anomalous_value": int(payment["amount"]) + 1,
            "expected_outcome": "Detect an allocation greater than its parent payment amount.",
        },
        {
            "issue_id": "ANOM-002",
            "issue_type": "SCHOLARSHIP_EXCEEDS_ELIGIBLE_FEES",
            "entity_name": "scholarships",
            "record_id": scholarship["scholarship_id"],
            "related_record_id": scholarship["invoice_id"],
            "source_value": int(scholarship["award_amount"]),
            "anomalous_value": int(scholarship_invoice["total_amount"]) + 1,
            "expected_outcome": "Detect an award greater than the related invoice fees.",
        },
        {
            "issue_id": "ANOM-003",
            "issue_type": "DUPLICATE_INVOICE_GENERATION",
            "entity_name": "invoices",
            "record_id": duplicate_invoice["invoice_id"],
            "related_record_id": duplicate_invoice["enrollment_id"],
            "source_value": 1,
            "anomalous_value": 2,
            "expected_outcome": "Detect two invoices generated for the same enrollment.",
        },
        {
            "issue_id": "ANOM-004",
            "issue_type": "REFUND_EXCEEDS_NET_PAID",
            "entity_name": "refunds",
            "record_id": refundable["payment_id"],
            "related_record_id": refundable["invoice_id"],
            "source_value": int(refundable["net_paid"]),
            "anomalous_value": int(refundable["net_paid"]) + 1,
            "expected_outcome": "Detect a refund greater than the payment's net amount allocated.",
        },
        {
            "issue_id": "ANOM-005",
            "issue_type": "BALANCE_DISAGREES_WITH_LEDGER",
            "entity_name": "student_balances",
            "record_id": balance["student_id"],
            "related_record_id": balance["student_id"],
            "source_value": int(balance["final_balance"]),
            "anomalous_value": int(balance["final_balance"]) + 1,
            "expected_outcome": "Detect a final balance that differs from its ledger-derived value.",
        },
    ])


def generate_student_balances(output_dir="data"):
    output_path = Path(output_dir)
    balances = build_student_balances(
        pd.read_csv(output_path / "students.csv"),
        pd.read_csv(output_path / "invoices.csv"),
        pd.read_csv(output_path / "scholarships.csv"),
        pd.read_csv(output_path / "payments.csv"),
        pd.read_csv(output_path / "payment_allocations.csv"),
        pd.read_csv(output_path / "refunds.csv"),
    )
    balances.to_csv(output_path / "student_balances.csv", index=False)
    return balances


def generate_ground_truth(payments, allocations, anomaly_cases):
    allocated = allocations.groupby("payment_id")["allocated_amount"].sum()
    rows = []
    for payment in payments.itertuples(index=False):
        unapplied_amount = int(payment.amount - allocated.get(payment.payment_id, 0))
        if unapplied_amount > 0:
            rows.append({
                "issue_id": f"ISS-{len(rows) + 1:06d}",
                "issue_type": "UNAPPLIED_PAYMENT_CREDIT",
                "record_id": payment.payment_id,
                "amount": unapplied_amount,
                "expected_outcome": "Payment must not exceed the total allocated amount; unapplied credit is tracked as an intentional anomaly.",
            })
    for case in anomaly_cases.itertuples(index=False):
        rows.append({
            "issue_id": case.issue_id,
            "issue_type": case.issue_type,
            "record_id": case.record_id,
            "amount": case.anomalous_value,
            "expected_outcome": case.expected_outcome,
        })
    return pd.DataFrame(rows, columns=["issue_id", "issue_type", "record_id", "amount", "expected_outcome"])


def export_json_exports(output_path, datasets):
    for name, frame in datasets.items():
        (output_path / f"{name}.json").write_text(frame.to_json(orient="records", indent=2), encoding="utf-8")


def export_sql_seed(output_path, datasets):
    primary_keys = {
        "students": "student_id",
        "programs": "program_id",
        "feeschedules": "fee_schedule_id",
        "enrollments": "enrollment_id",
        "invoices": "invoice_id",
        "invoice_lines": "line_id",
        "eligibility": "eligibility_id",
        "scholarships": "scholarship_id",
        "payments": "payment_id",
        "payment_allocations": "allocation_id",
        "refunds": "refund_id",
        "student_balances": "student_id",
        "ground_truth": "issue_id",
        "anomaly_cases": "issue_id",
    }

    def sql_literal(value):
        if pd.isna(value):
            return "NULL"
        if isinstance(value, str):
            return "'" + value.replace("'", "''") + "'"
        return str(value)

    with (output_path / "seed_data.sql").open("w", encoding="utf-8", newline="\n") as sql_file:
        sql_file.write("BEGIN;\n\n")
        for name, frame in datasets.items():
            columns = list(frame.columns)
            quoted_columns = ", ".join(f'"{column}"' for column in columns)
            definitions = []
            for column, dtype in frame.dtypes.items():
                if pd.api.types.is_integer_dtype(dtype):
                    sql_type = "INTEGER"
                elif pd.api.types.is_float_dtype(dtype):
                    sql_type = "REAL"
                else:
                    sql_type = "TEXT"
                primary_key = " PRIMARY KEY" if column == primary_keys.get(name) else ""
                definitions.append(f'"{column}" {sql_type}{primary_key}')
            sql_file.write(
                f'CREATE TABLE IF NOT EXISTS "{name}" '
                f'({", ".join(definitions)});\n'
            )
            insert_prefix = f'INSERT INTO "{name}" ({quoted_columns}) VALUES '
            rows = iter(frame.itertuples(index=False, name=None))
            while True:
                batch = []
                for _ in range(100):
                    try:
                        batch.append(next(rows))
                    except StopIteration:
                        break
                if not batch:
                    break
                sql_file.write(
                    insert_prefix
                    + ", ".join(
                        "(" + ", ".join(sql_literal(value) for value in row) + ")"
                        for row in batch
                    )
                    + ";\n"
                )
            sql_file.write("\n")
        sql_file.write("COMMIT;\n")


def build_source_manifest(output_path, seed, scale, row_counts):
    manifest = {
        "dataset_name": f"yottaflex-{scale}",
        "generation_method": "synthetic deterministic generator",
        "random_seed": seed,
        "generation_date": "2026-10-31",
        "dataset_version": "1.0.0",
        "row_counts": row_counts,
        "lawful_provenance": "Entirely synthetic data generated for testing and validation only; no real personal information used.",
    }
    (output_path / "source_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def validate_row_counts(row_counts, expected):
    issues = []
    for key, expected_value in expected.items():
        actual = row_counts.get(key)
        if actual != expected_value:
            issues.append(f"{key}: expected {expected_value}, got {actual}")
    return issues


def generate_all(output_dir="data", seed=SEED, scale="full", student_count=None, program_count=None, term_ids=None):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    if scale == "full":
        if student_count not in (None, 10_000):
            raise ValueError("Full mode requires exactly 10,000 students.")
        if program_count not in (None, 20):
            raise ValueError("Full mode requires exactly 20 programs.")
        if term_ids is not None and list(term_ids) != DEFAULT_TERMS:
            raise ValueError("Full mode requires the configured three academic terms.")
    config = resolve_dataset_config(
        scale=scale,
        student_count=student_count,
        program_count=program_count,
        term_ids=term_ids,
    )
    rng = random.Random(seed)

    total_started = time.perf_counter()

    def run_stage(number, label, operation, record_count):
        stage_started = time.perf_counter()
        print(f"[{number}/10] Generating {label}...", flush=True)
        result = operation()
        elapsed = time.perf_counter() - stage_started
        print(
            f"    {record_count(result):,} records in {elapsed:.2f}s",
            flush=True,
        )
        return result

    students = run_stage(
        1, "students",
        lambda: generate_students(
            rng, config["student_count"], force_active=(scale == "full")
        ),
        len,
    )
    programs = run_stage(
        2, "programs",
        lambda: generate_programs(rng, config["program_count"]),
        len,
    )
    fee_schedules = run_stage(
        3, "fee schedules",
        lambda: generate_fee_schedules(programs, rng, config["term_ids"]),
        len,
    )
    enrollments, eligibility = run_stage(
        4, "enrollments and eligibility",
        lambda: (
            generate_enrollments(
                students, programs, rng, config["term_ids"],
                full_dataset=(scale == "full"),
            ),
            generate_eligibility(
                students, rng, full_dataset=(scale == "full")
            ),
        ),
        lambda result: len(result[0]) + len(result[1]),
    )
    def generate_invoice_outputs():
        invoices = generate_invoices(enrollments, fee_schedules)
        return invoices, generate_invoice_lines(invoices, fee_schedules)

    invoices, invoice_lines = run_stage(
        5, "invoices and invoice lines",
        generate_invoice_outputs,
        lambda result: len(result[0]) + len(result[1]),
    )
    scholarships = run_stage(
        6, "scholarships",
        lambda: generate_scholarships(
            enrollments,
            invoices,
            eligibility,
            rng,
            target_count=15_000 if scale == "full" else 1_500,
        ),
        len,
    )
    payments, allocations = run_stage(
        7, "payments and allocations",
        lambda: generate_payments(
            invoices,
            scholarships,
            rng,
            target_count=50_000 if scale == "full" else 5_000,
        ),
        lambda result: len(result[0]) + len(result[1]),
    )

    def generate_financial_outputs():
        refunds = generate_refunds(payments, allocations, rng)
        updated_invoices = update_invoice_statuses(
            invoices, scholarships, allocations, refunds
        )
        balances = build_student_balances(
            students, updated_invoices, scholarships, payments, allocations, refunds
        )
        anomaly_cases = generate_anomaly_cases(
            updated_invoices, scholarships, payments, allocations, refunds, balances
        )
        ground_truth = generate_ground_truth(
            payments, allocations, anomaly_cases
        )
        return updated_invoices, refunds, balances, anomaly_cases, ground_truth

    invoices, refunds, balances, anomaly_cases, ground_truth = run_stage(
        8, "refunds, balances, and anomaly labels",
        generate_financial_outputs,
        lambda result: sum(len(frame) for frame in result),
    )

    datasets = {
        "students": students,
        "programs": programs,
        "feeschedules": fee_schedules,
        "enrollments": enrollments,
        "invoices": invoices,
        "invoice_lines": invoice_lines,
        "eligibility": eligibility,
        "scholarships": scholarships,
        "payments": payments,
        "payment_allocations": allocations,
        "refunds": refunds,
        "student_balances": balances,
        "anomaly_cases": anomaly_cases,
        "ground_truth": ground_truth,
    }

    def export_tabular_datasets():
        for name, frame in datasets.items():
            frame.to_csv(output_path / f"{name}.csv", index=False)
        export_json_exports(output_path, datasets)
        return sum(len(frame) for frame in datasets.values())

    run_stage(9, "CSV and JSON exports", export_tabular_datasets, lambda count: count)
    row_counts = {name: len(frame) for name, frame in datasets.items()}
    if scale == "full":
        expected_full_counts = {
            "students": 10_000,
            "programs": 20,
            "enrollments": 30_000,
            "invoices": 30_000,
            "scholarships": 15_000,
            "payments": 50_000,
            "payment_allocations": 50_000,
        }
        count_issues = validate_row_counts(row_counts, expected_full_counts)
        if count_issues:
            raise RuntimeError("Full-mode volume check failed: " + "; ".join(count_issues))

    def export_sql_and_manifest():
        export_sql_seed(output_path, datasets)
        build_source_manifest(output_path, seed, scale, row_counts)
        return sum(len(frame) for frame in datasets.values())

    run_stage(10, "SQL and manifest exports", export_sql_and_manifest, lambda count: count)
    print(
        f"Generation complete: {sum(row_counts.values()):,} total records; "
        f"output folder: {output_path}; total time: "
        f"{time.perf_counter() - total_started:.2f}s",
        flush=True,
    )
    return datasets


def main():
    parser = argparse.ArgumentParser(description="Generate YottaFlex synthetic datasets.")
    parser.add_argument(
        "--mode",
        choices=sorted(DATASET_SCHEMES),
        default="full",
        help="Dataset size to generate (default: full).",
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Directory for generated CSV, JSON, and SQL files (default: data).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help=f"Random seed (default: {SEED}).",
    )
    args = parser.parse_args()
    generate_all(output_dir=args.output_dir, seed=args.seed, scale=args.mode)


if __name__ == "__main__":
    main()
