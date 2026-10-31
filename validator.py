
import argparse
import time
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
	"students": ["student_id", "student_name", "status"],
	"programs": ["program_id", "program_name", "duration_years", "tuition_fee"],
	"feeschedules": ["fee_schedule_id", "program_id", "term_id", "tuition_fee", "lab_fee", "exam_fee"],
	"enrollments": ["enrollment_id", "student_id", "program_id", "term_id", "status"],
	"invoices": [
		"invoice_id", "enrollment_id", "student_id", "fee_schedule_id",
		"invoice_date", "due_date", "total_amount", "status",
	],
	"invoice_lines": ["line_id", "invoice_id", "fee_type", "amount"],
	"eligibility": ["eligibility_id", "student_id", "gpa", "family_income", "eligible"],
	"scholarships": ["scholarship_id", "student_id", "enrollment_id", "invoice_id", "award_amount", "status"],
	"payments": ["payment_id", "student_id", "payment_date", "amount", "payment_method"],
	"payment_allocations": ["allocation_id", "payment_id", "invoice_id", "allocated_amount"],
	"refunds": ["refund_id", "student_id", "payment_id", "refund_amount", "reason"],
	"student_balances": [
		"student_id", "invoice_total", "scholarship_total", "payment_total",
		"allocated_payment_total", "refund_total", "final_balance",
	],
	"ground_truth": ["issue_id", "issue_type", "record_id", "amount", "expected_outcome"],
	"anomaly_cases": [
		"issue_id", "issue_type", "entity_name", "record_id", "related_record_id",
		"source_value", "anomalous_value", "expected_outcome",
	],
}

PRIMARY_KEYS = {
	"students": ["student_id"],
	"programs": ["program_id"],
	"feeschedules": ["fee_schedule_id"],
	"enrollments": ["enrollment_id"],
	"invoices": ["invoice_id"],
	"invoice_lines": ["line_id"],
	"eligibility": ["eligibility_id"],
	"scholarships": ["scholarship_id"],
	"payments": ["payment_id"],
	"payment_allocations": ["allocation_id"],
	"refunds": ["refund_id"],
	"student_balances": ["student_id"],
	"ground_truth": ["issue_id"],
	"anomaly_cases": ["issue_id"],
}


def validate_data(data_dir="data"):
	data_path = Path(data_dir)
	frames = {}
	issues = []

	for name, required_columns in REQUIRED_COLUMNS.items():
		file_path = data_path / f"{name}.csv"
		if not file_path.exists():
			issues.append(f"Missing required file: {file_path}")
			continue
		frame = pd.read_csv(file_path)
		missing_columns = sorted(set(required_columns) - set(frame.columns))
		if missing_columns:
			issues.append(f"{name}.csv is missing columns: {', '.join(missing_columns)}")
			continue
		frames[name] = frame

	if issues:
		return issues

	def report_rows(label, invalid_rows):
		count = int(invalid_rows.sum())
		if count:
			issues.append(f"{label}: {count} invalid row(s)")

	def check_foreign_key(child, child_column, parent, parent_column):
		report_rows(
			f"{child}.{child_column} references {parent}.{parent_column}",
			~frames[child][child_column].isin(frames[parent][parent_column]),
		)

	for name, key_columns in PRIMARY_KEYS.items():
		report_rows(f"{name} primary key uniqueness", frames[name].duplicated(key_columns))
		report_rows(f"{name} primary key nulls", frames[name][key_columns].isna().any(axis=1))

	for child, child_column, parent, parent_column in [
		("feeschedules", "program_id", "programs", "program_id"),
		("enrollments", "student_id", "students", "student_id"),
		("enrollments", "program_id", "programs", "program_id"),
		("invoices", "enrollment_id", "enrollments", "enrollment_id"),
		("invoices", "fee_schedule_id", "feeschedules", "fee_schedule_id"),
		("invoice_lines", "invoice_id", "invoices", "invoice_id"),
		("eligibility", "student_id", "students", "student_id"),
		("scholarships", "student_id", "students", "student_id"),
		("scholarships", "enrollment_id", "enrollments", "enrollment_id"),
		("scholarships", "invoice_id", "invoices", "invoice_id"),
		("payments", "student_id", "students", "student_id"),
		("payment_allocations", "payment_id", "payments", "payment_id"),
		("payment_allocations", "invoice_id", "invoices", "invoice_id"),
		("refunds", "student_id", "students", "student_id"),
		("refunds", "payment_id", "payments", "payment_id"),
		("student_balances", "student_id", "students", "student_id"),
	]:
		check_foreign_key(child, child_column, parent, parent_column)

	schedules = frames["feeschedules"]
	report_rows(
		"Fee schedule uniqueness by program and term",
		schedules.duplicated(["program_id", "term_id"]),
	)
	enrollments = frames["enrollments"]
	report_rows(
		"Enrollment uniqueness by student and term",
		enrollments.duplicated(["student_id", "term_id"]),
	)
	schedule_pairs = set(zip(schedules["program_id"], schedules["term_id"]))
	report_rows(
		"Enrollment has a fee schedule for its program and term",
		pd.Series([
			(program_id, term_id) not in schedule_pairs
			for program_id, term_id in zip(enrollments["program_id"], enrollments["term_id"])
		]),
	)

	invoices = frames["invoices"]
	report_rows(
		"Duplicate invoice generation by enrollment",
		invoices.duplicated(["enrollment_id"]),
	)
	invoice_enrollments = invoices.merge(
		enrollments[["enrollment_id", "student_id", "program_id", "term_id", "status"]],
		on="enrollment_id", how="left", suffixes=("_invoice", "_enrollment"),
	)
	report_rows(
		"Invoice student matches enrollment",
		invoice_enrollments["student_id_invoice"] != invoice_enrollments["student_id_enrollment"],
	)
	report_rows(
		"Invoices are generated only for active enrollments",
		invoice_enrollments["status_enrollment"] != "ACTIVE",
	)

	invoice_schedules = invoices.merge(
		schedules[["fee_schedule_id", "program_id", "term_id", "tuition_fee", "lab_fee", "exam_fee"]],
		on="fee_schedule_id", how="left",
	)
	invoice_schedule_context = invoice_enrollments.merge(
		schedules[["fee_schedule_id", "program_id", "term_id"]],
		on="fee_schedule_id", how="left", suffixes=("_enrollment", "_schedule"),
	)
	report_rows(
		"Invoice schedule matches enrollment program and term",
		(invoice_schedule_context["program_id_enrollment"] != invoice_schedule_context["program_id_schedule"])
		| (invoice_schedule_context["term_id_enrollment"] != invoice_schedule_context["term_id_schedule"]),
	)
	schedule_totals = (
		invoice_schedules["tuition_fee"]
		+ invoice_schedules["lab_fee"]
		+ invoice_schedules["exam_fee"]
	)
	report_rows("Invoice total matches fee schedule", invoices["total_amount"] != schedule_totals)
	for table, column in [
		("invoices", "invoice_date"),
		("invoices", "due_date"),
		("payments", "payment_date"),
	]:
		parsed_dates = pd.to_datetime(frames[table][column], errors="coerce")
		report_rows(f"{table}.{column} is a valid date", parsed_dates.isna())
	report_rows(
		"Invoice due dates do not precede invoice dates",
		pd.to_datetime(invoices["due_date"], errors="coerce")
		< pd.to_datetime(invoices["invoice_date"], errors="coerce"),
	)
	for name, column, allowed in [
		("students", "status", {"ACTIVE", "INACTIVE"}),
		("enrollments", "status", {"ACTIVE", "WITHDRAWN"}),
		("invoices", "status", {"OPEN", "PARTIAL", "PAID"}),
		("payments", "payment_method", {"UPI", "CARD", "BANK_TRANSFER"}),
		("refunds", "reason", {"WITHDRAWAL", "OVERPAYMENT", "FEE_ADJUSTMENT"}),
	]:
		report_rows(f"{name}.{column} allowed values", ~frames[name][column].isin(allowed))

	invoice_lines = frames["invoice_lines"]
	report_rows(
		"Invoice line uniqueness by invoice and fee type",
		invoice_lines.duplicated(["invoice_id", "fee_type"]),
	)
	valid_fee_types = {"TUITION", "LAB", "EXAM"}
	report_rows("Invoice line fee type", ~invoice_lines["fee_type"].isin(valid_fee_types))
	line_totals = invoice_lines.groupby("invoice_id")["amount"].sum()
	report_rows(
		"Invoice line totals reconcile to invoice total",
		invoices["total_amount"].to_numpy()
		!= invoices["invoice_id"].map(line_totals).fillna(0).to_numpy(),
	)
	line_types = invoice_lines.groupby("invoice_id")["fee_type"].agg(set)
	report_rows(
		"Each invoice has tuition, lab, and exam lines",
		~invoices["invoice_id"].map(line_types).map(lambda value: value == valid_fee_types).fillna(False),
	)

	eligibility = frames["eligibility"].set_index("student_id")
	eligibility_rule = (eligibility["gpa"] >= 7.5) & (eligibility["family_income"] <= 400_000)
	report_rows(
		"Eligibility flag matches GPA and income rules",
		eligibility["eligible"] != eligibility_rule.map({True: "YES", False: "NO"}),
	)
	scholarships = frames["scholarships"]
	report_rows("Only approved scholarships are written", scholarships["status"] != "APPROVED")
	report_rows(
		"Scholarships are awarded only to eligible students",
		scholarships["student_id"].map(eligibility["eligible"]) != "YES",
	)
	scholarship_invoice = scholarships.merge(
		invoices[["invoice_id", "student_id", "enrollment_id", "total_amount"]],
		on="invoice_id", how="left", suffixes=("_scholarship", "_invoice"),
	)
	report_rows(
		"Scholarship student and enrollment match invoice",
		(scholarship_invoice["student_id_scholarship"] != scholarship_invoice["student_id_invoice"])
		| (scholarship_invoice["enrollment_id_scholarship"] != scholarship_invoice["enrollment_id_invoice"]),
	)
	scholarship_totals = scholarships.groupby("invoice_id")["award_amount"].sum()
	report_rows(
		"Scholarships do not exceed invoice totals",
		invoices["invoice_id"].map(scholarship_totals).fillna(0).to_numpy() > invoices["total_amount"].to_numpy(),
	)
	scholarship_invoice_amounts = scholarships.merge(
		invoices[["invoice_id", "total_amount"]], on="invoice_id", how="left"
	)
	report_rows(
		"Scholarship award caps",
		scholarship_invoice_amounts["award_amount"]
		> scholarship_invoice_amounts["total_amount"].mul(0.5).clip(upper=20_000),
	)

	payments = frames["payments"]
	allocations = frames["payment_allocations"]
	report_rows("Payment amounts are positive", payments["amount"] <= 0)
	report_rows("Allocation amounts are positive", allocations["allocated_amount"] <= 0)
	allocated_by_payment = allocations.groupby("payment_id")["allocated_amount"].sum()
	report_rows(
		"Payment allocations do not exceed payment amount",
		payments["payment_id"].map(allocated_by_payment).fillna(0).to_numpy() > payments["amount"].to_numpy(),
	)
	allocation_context = allocations.merge(
		payments[["payment_id", "student_id"]].rename(columns={"student_id": "payment_student_id"}),
		on="payment_id", how="left",
	).merge(
		invoices[["invoice_id", "student_id"]].rename(columns={"student_id": "invoice_student_id"}),
		on="invoice_id", how="left",
	)
	report_rows(
		"Allocation payment student matches invoice student",
		allocation_context["payment_student_id"] != allocation_context["invoice_student_id"],
	)
	applied_by_invoice = allocations.groupby("invoice_id")["allocated_amount"].sum()
	net_invoice_due = invoices["total_amount"] - invoices["invoice_id"].map(scholarship_totals).fillna(0)
	report_rows(
		"Invoice allocations do not exceed net invoice due",
		invoices["invoice_id"].map(applied_by_invoice).fillna(0).to_numpy() > net_invoice_due.to_numpy(),
	)

	refunds = frames["refunds"]
	report_rows("Refund amounts are positive", refunds["refund_amount"] <= 0)
	refund_context = refunds.merge(
		payments[["payment_id", "student_id"]], on="payment_id", how="left", suffixes=("_refund", "_payment"),
	)
	report_rows(
		"Refund student matches payment student",
		refund_context["student_id_refund"] != refund_context["student_id_payment"],
	)
	refund_totals = refunds.groupby("payment_id")["refund_amount"].sum()
	report_rows(
		"Refunds do not exceed allocated payment amount",
		payments["payment_id"].map(refund_totals).fillna(0).to_numpy()
		> payments["payment_id"].map(allocated_by_payment).fillna(0).to_numpy(),
	)

	refunded_invoice_context = refunds.merge(
		allocations[["payment_id", "invoice_id"]], on="payment_id", how="left",
	)
	refunded_by_invoice = refunded_invoice_context.groupby("invoice_id")["refund_amount"].sum()
	net_paid_by_invoice = (
		invoices["invoice_id"].map(applied_by_invoice).fillna(0)
		- invoices["invoice_id"].map(refunded_by_invoice).fillna(0)
	)
	expected_outstanding = net_invoice_due - net_paid_by_invoice
	expected_status = pd.Series("OPEN", index=invoices.index)
	expected_status.loc[net_paid_by_invoice > 0] = "PARTIAL"
	expected_status.loc[expected_outstanding <= 0] = "PAID"
	report_rows("Invoice status matches net payments and refunds", invoices["status"] != expected_status)

	balances = frames["student_balances"]
	report_rows(
		"Balance rows cover every student exactly once",
		~frames["students"]["student_id"].isin(balances["student_id"]),
	)
	invoice_by_student = invoices.groupby("student_id")["total_amount"].sum()
	scholarship_by_student = scholarships.groupby("student_id")["award_amount"].sum()
	payment_by_student = payments.groupby("student_id")["amount"].sum()
	allocation_students = allocations.merge(
		invoices[["invoice_id", "student_id"]], on="invoice_id", how="left",
	)
	allocated_by_student = allocation_students.groupby("student_id")["allocated_amount"].sum()
	refund_by_student = refunds.groupby("student_id")["refund_amount"].sum()
	for column, grouped in [
		("invoice_total", invoice_by_student),
		("scholarship_total", scholarship_by_student),
		("payment_total", payment_by_student),
		("allocated_payment_total", allocated_by_student),
		("refund_total", refund_by_student),
	]:
		expected = balances["student_id"].map(grouped).fillna(0)
		report_rows(f"Student balance {column} reconciles", balances[column] != expected)
	expected_balance = (
		balances["invoice_total"]
		- balances["scholarship_total"]
		- balances["payment_total"]
		+ balances["refund_total"]
	)
	report_rows("Final student balance formula", balances["final_balance"] != expected_balance)

	unapplied = payments.assign(
		allocated=payments["payment_id"].map(allocated_by_payment).fillna(0)
	)
	unapplied = unapplied.loc[unapplied["amount"] > unapplied["allocated"]]
	expected_ground_truth = {
		("UNAPPLIED_PAYMENT_CREDIT", row.payment_id, int(row.amount - row.allocated))
		for row in unapplied.itertuples()
	}
	anomaly_cases = frames["anomaly_cases"]
	expected_case_types = {
		"PAYMENT_ALLOCATION_EXCEEDS_PAYMENT",
		"SCHOLARSHIP_EXCEEDS_ELIGIBLE_FEES",
		"DUPLICATE_INVOICE_GENERATION",
		"REFUND_EXCEEDS_NET_PAID",
		"BALANCE_DISAGREES_WITH_LEDGER",
	}
	report_rows(
		"All five required anomaly scenarios are present",
		pd.Series([set(anomaly_cases["issue_type"]) != expected_case_types]),
	)
	report_rows(
		"Anomaly scenario types are unique",
		anomaly_cases["issue_type"].duplicated(),
	)

	payments_by_id = payments.set_index("payment_id")
	allocations_by_id = allocations.set_index("allocation_id")
	scholarships_by_id = scholarships.set_index("scholarship_id")
	invoices_by_id = invoices.set_index("invoice_id")
	balances_by_id = balances.set_index("student_id")
	case_checks = []
	expected_case_ground_truth = set()
	for case in anomaly_cases.itertuples(index=False):
		expected_case_ground_truth.add(
			(case.issue_type, case.record_id, int(case.anomalous_value))
		)
		if case.issue_type == "PAYMENT_ALLOCATION_EXCEEDS_PAYMENT":
			if (
				case.record_id in payments_by_id.index
				and case.related_record_id in allocations_by_id.index
			):
				payment = payments_by_id.loc[case.record_id]
				allocation = allocations_by_id.loc[case.related_record_id]
				case_checks.append(
					case.source_value == payment["amount"]
					and allocation["payment_id"] == case.record_id
					and case.anomalous_value > payment["amount"]
				)
			else:
				case_checks.append(False)
		elif case.issue_type == "SCHOLARSHIP_EXCEEDS_ELIGIBLE_FEES":
			if (
				case.record_id in scholarships_by_id.index
				and case.related_record_id in invoices_by_id.index
			):
				scholarship = scholarships_by_id.loc[case.record_id]
				invoice = invoices_by_id.loc[case.related_record_id]
				case_checks.append(
					scholarship["invoice_id"] == case.related_record_id
					and case.source_value == scholarship["award_amount"]
					and case.anomalous_value > invoice["total_amount"]
				)
			else:
				case_checks.append(False)
		elif case.issue_type == "DUPLICATE_INVOICE_GENERATION":
			if case.record_id in invoices_by_id.index:
				invoice = invoices_by_id.loc[case.record_id]
				invoice_count = int(
					(invoices["enrollment_id"] == case.related_record_id).sum()
				)
				case_checks.append(
					invoice["enrollment_id"] == case.related_record_id
					and case.source_value == invoice_count
					and case.anomalous_value > invoice_count
				)
			else:
				case_checks.append(False)
		elif case.issue_type == "REFUND_EXCEEDS_NET_PAID":
			payment_allocations = allocations.loc[
				allocations["payment_id"] == case.record_id
			]
			net_paid = int(payment_allocations["allocated_amount"].sum())
			net_paid -= int(refund_totals.get(case.record_id, 0))
			case_checks.append(
				not payment_allocations.empty
				and case.related_record_id in set(payment_allocations["invoice_id"])
				and case.source_value == net_paid
				and case.anomalous_value > net_paid
			)
		elif case.issue_type == "BALANCE_DISAGREES_WITH_LEDGER":
			if case.record_id in balances_by_id.index:
				balance = balances_by_id.loc[case.record_id]
				case_checks.append(
					case.source_value == balance["final_balance"]
					and case.anomalous_value != balance["final_balance"]
				)
			else:
				case_checks.append(False)
		else:
			case_checks.append(False)
		case_checks[-1] = bool(
			case_checks[-1]
			and isinstance(case.expected_outcome, str)
			and bool(case.expected_outcome.strip())
		)

	report_rows(
		"Anomaly scenario evidence",
		pd.Series([not result for result in case_checks]),
	)
	expected_ground_truth |= expected_case_ground_truth
	actual_ground_truth = set(
		zip(
			frames["ground_truth"]["issue_type"],
			frames["ground_truth"]["record_id"],
			frames["ground_truth"]["amount"].astype(int),
		)
	)
	report_rows(
		"Ground truth matches detected anomaly scenarios",
		pd.Series([actual_ground_truth != expected_ground_truth]),
	)

	return issues


def main():
	parser = argparse.ArgumentParser(description="Validate generated YottaFlex datasets.")
	parser.add_argument(
		"--data-dir",
		default="data",
		help="Directory containing the generated datasets (default: data).",
	)
	args = parser.parse_args()
	started = time.perf_counter()
	issues = validate_data(args.data_dir)
	if issues:
		print("Dataset validation failed:")
		for issue in issues:
			print(f"- {issue}")
		print(f"Validation time: {time.perf_counter() - started:.2f}s")
		raise SystemExit(1)
	anomaly_cases = pd.read_csv(Path(args.data_dir) / "anomaly_cases.csv")
	print(
		"Dataset validation passed: keys, relationships, business rules, "
		"and financial calculations reconcile."
	)
	print(
		f"Detected intentional anomaly scenarios: "
		f"{anomaly_cases['issue_type'].nunique()}/5"
	)
	print(f"Validation time: {time.perf_counter() - started:.2f}s")


if __name__ == "__main__":
	main()