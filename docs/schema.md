# Schema Overview

## Core tables

### students
- Primary key: `student_id`
- Business purpose: student roster
- Key columns: `student_id`, `student_name`, `status`

### programs
- Primary key: `program_id`
- Business purpose: academic offerings
- Key columns: `program_id`, `program_name`, `duration_years`, `tuition_fee`

### feeschedules
- Primary key: `fee_schedule_id`
- Foreign keys: `program_id` -> `programs.program_id`
- Business purpose: program and term pricing
- Key columns: `fee_schedule_id`, `program_id`, `term_id`, `tuition_fee`, `lab_fee`, `exam_fee`

### enrollments
- Primary key: `enrollment_id`
- Foreign keys: `student_id` -> `students.student_id`, `program_id` -> `programs.program_id`
- Business purpose: program and term enrollment state
- Lifecycle states: `ACTIVE`, `WITHDRAWN`

### invoices
- Primary key: `invoice_id`
- Foreign keys: `enrollment_id` -> `enrollments.enrollment_id`, `fee_schedule_id` -> `feeschedules.fee_schedule_id`
- Business purpose: term-based billing for active enrollments
- Lifecycle states: `OPEN`, `PARTIAL`, `PAID`

### invoice_lines
- Primary key: `line_id`
- Foreign key: `invoice_id` -> `invoices.invoice_id`
- Business purpose: itemized fee components
- Allowed fee types: `TUITION`, `LAB`, `EXAM`

### eligibility
- Primary key: `eligibility_id`
- Foreign key: `student_id` -> `students.student_id`
- Business purpose: eligibility evaluation for financial aid
- Rule: `eligible = YES` when GPA >= 7.5 and family income <= 400000

### scholarships
- Primary key: `scholarship_id`
- Foreign keys: `student_id` -> `students.student_id`, `enrollment_id` -> `enrollments.enrollment_id`, `invoice_id` -> `invoices.invoice_id`
- Business purpose: approved aid awards
- Status: `APPROVED`

### payments
- Primary key: `payment_id`
- Foreign key: `student_id` -> `students.student_id`
- Business purpose: cash received from students
- `amount` is gross cash received

### payment_allocations
- Primary key: `allocation_id`
- Foreign keys: `payment_id` -> `payments.payment_id`, `invoice_id` -> `invoices.invoice_id`
- Business purpose: allocation of payments to invoice balances

### refunds
- Primary key: `refund_id`
- Foreign keys: `student_id` -> `students.student_id`, `payment_id` -> `payments.payment_id`
- Business purpose: refunds against a payment allocation

### student_balances
- Primary key: `student_id`
- Foreign key: `student_id` -> `students.student_id`
- Business purpose: aggregate student ledger totals

### anomaly_cases
- Primary key: `issue_id`
- Business purpose: isolated, labelled anomaly scenario inputs
- Key columns: `issue_type`, `entity_name`, `record_id`, `related_record_id`, `source_value`, `anomalous_value`, `expected_outcome`
- The scenario describes an intentionally invalid value without changing the referenced baseline record.

### ground_truth
- Primary key: `issue_id`
- Business purpose: labels known unapplied credits and the five required anomaly scenarios
- The table is kept separate from normal source features.

## Relationship summary

- One-to-many: `students` to `enrollments`, `payments`, `refunds`, `eligibility`
- One-to-many: `programs` to `feeschedules` and `enrollments`
- One-to-many: `enrollments` to `invoices` and `scholarships`
- One-to-many: `invoices` to `invoice_lines` and `payment_allocations`
- One-to-many: `payments` to `payment_allocations` and `refunds`

## Cardinality notes

- A fee schedule is defined per `program_id` and `term_id`.
- A student may have multiple enrollments across program and term combinations.
- Each invoice is tied to exactly one active enrollment and one fee schedule.
- An invoice may receive multiple allocations from different payments.
- A payment may be allocated to multiple invoices.
- A refund always references a payment and a student.
- Each `anomaly_cases` row points to baseline records relevant to its issue type; the anomaly value exists only in the scenario row.

## Lifecycle and dates

- Enrollment lifecycle: `ACTIVE` and `WITHDRAWN`
- Invoice lifecycle: `OPEN`, `PARTIAL`, `PAID`
- Effective dates are modeled as simplified synthetic dates for validation logic and testing

## Anomaly scenarios and baseline integrity

The required allocation-over-payment, scholarship-over-fees, duplicate-invoice, refund-over-net-paid, and balance-mismatch examples are stored in `anomaly_cases`. `ground_truth` labels each with an issue ID and expected outcome. Validation compares each scenario value with its source records and checks that all five cases are present. Baseline rows remain clean and are independently validated.

## Data integrity guarantees

The generator keeps IDs deterministic and zero-padded where specified. Baseline foreign keys and reconciliations are validated. CSV and JSON files have matching records; the SQL seed contains the same tables and row counts. The model currently does not include event-sourced lifecycle history, late-fee policies, waiver transactions, or explicit withdrawal/cancellation events.
