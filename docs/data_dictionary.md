# Data Dictionary

All monetary amounts are integer units in a fictional currency. IDs are synthetic strings. The default generation seed is `20261022`. Full-mode row counts are fixed by the assignment requirements. Intentional anomaly examples are recorded separately and do not alter baseline ledger records.

## Entity Files

| File | Primary key | Columns and meaning |
| --- | --- | --- |
| `students.csv` | `student_id` | `student_id`, `student_name`, `status` (`ACTIVE` or `INACTIVE`). |
| `programs.csv` | `program_id` | `program_id`, `program_name`, `duration_years`, `tuition_fee` (program's base tuition). |
| `feeschedules.csv` | `fee_schedule_id` | `fee_schedule_id`, `program_id`, `term_id`, `tuition_fee`, `lab_fee`, `exam_fee`. One schedule per program and term. |
| `enrollments.csv` | `enrollment_id` | `enrollment_id`, `student_id`, `program_id`, `term_id`, `status` (`ACTIVE` or `WITHDRAWN`). Only active students are enrolled; only active enrollments are invoiced. |
| `eligibility.csv` | `eligibility_id` | `eligibility_id`, `student_id`, `gpa`, `family_income`, `eligible`. Eligibility is `YES` when GPA is at least 7.5 and family income is at most 400,000. |
| `invoices.csv` | `invoice_id` | `invoice_id`, `enrollment_id`, `student_id`, `fee_schedule_id`, `invoice_date`, `due_date`, `total_amount`, `status` (`OPEN`, `PARTIAL`, or `PAID`). One invoice is generated for each active enrollment. |
| `invoice_lines.csv` | `line_id` | `line_id`, `invoice_id`, `fee_type` (`TUITION`, `LAB`, `EXAM`), `amount`. The three line amounts equal the invoice's fee-schedule total. |
| `scholarships.csv` | `scholarship_id` | `scholarship_id`, `student_id`, `enrollment_id`, `invoice_id`, `award_amount`, `status` (`APPROVED`). Awards are limited to eligible students and do not exceed half of an invoice or 20,000. |
| `payments.csv` | `payment_id` | `payment_id`, `student_id`, `payment_date`, `amount`, `payment_method` (`UPI`, `CARD`, or `BANK_TRANSFER`). Payment amount is gross cash received. |
| `payment_allocations.csv` | `allocation_id` | `allocation_id`, `payment_id`, `invoice_id`, `allocated_amount`. An allocation applies payment to an invoice; per-payment allocations do not exceed payment amount, and per-invoice allocations do not exceed invoice amount after scholarships. |
| `refunds.csv` | `refund_id` | `refund_id`, `student_id`, `payment_id`, `refund_amount`, `reason` (`WITHDRAWAL`, `OVERPAYMENT`, or `FEE_ADJUSTMENT`). Refunds reference a student's payment and cannot exceed its allocated amount. |
| `student_balances.csv` | `student_id` | `student_id`, `invoice_total`, `scholarship_total`, `payment_total` (gross payments), `allocated_payment_total`, `refund_total`, `final_balance`. Includes all students, even those without financial activity. |
| `anomaly_cases.csv` | `issue_id` | `issue_id`, `issue_type`, `entity_name`, `record_id`, `related_record_id`, `source_value`, `anomalous_value`, `expected_outcome`. Holds five deliberately invalid scenario values independently from the baseline tables. |
| `ground_truth.csv` | `issue_id` | `issue_id`, `issue_type`, `record_id`, `amount`, `expected_outcome`. Labels unapplied payment credits and the five anomaly scenarios. |

## Relationships

- `feeschedules.program_id` references `programs.program_id`.
- `enrollments.student_id` and `enrollments.program_id` reference students and programs.
- Each invoice references its enrollment and fee schedule; its student, program, and term must agree with those parent records.
- Invoice lines reference invoices. Each invoice has one line for each of the three fee types.
- Eligibility and scholarship rows reference students. Scholarships also reference the same enrollment and invoice as the recipient.
- Payments and refunds reference students; allocations reference both payments and invoices; refunds reference payments.
- Student balances reference the complete student roster.
- `anomaly_cases` references baseline IDs to describe how an intentionally modified scenario would violate a rule; it does not change the referenced baseline record.

## Reconciliation

For each invoice:

```text
invoice total = tuition line + lab line + exam line
outstanding = invoice total - approved scholarships - allocated payments + refunds
```

Invoice status is `PAID` when outstanding is zero or less, `PARTIAL` when some net payment has been applied, and otherwise `OPEN`.

For each student:

```text
final balance = invoice total - approved scholarships - gross payments + refunds
```

Unapplied payment amounts are not allocated to invoices, but remain in gross payments and therefore can result in a negative (credit) balance. `allocated_payment_total` is reported separately so applied cash can be distinguished from unapplied credit.

## Deliberate anomaly scenarios

The five required invalid values are represented in `anomaly_cases.csv` and labelled in `ground_truth.csv`. Their values are validated against the clean source records. Keeping these as scenario data avoids contaminating baseline balances, foreign keys, or the full-mode required row counts.
