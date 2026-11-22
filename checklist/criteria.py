"""HarbourLine Finance's mandatory-evidence rules (GENERATED, synthetic policy for the prototype).

Each criterion is keyed by name and version, says when it applies, names the structured fields it reads and
the inputs the model must extract, and decides its item with a deterministic check.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

SATISFIED, EXCEPTION, UNABLE = "satisfied", "exception", "unable to verify"
FINANCIALS_THRESHOLD = 150_000
CREDIT_REPORT_MAX_AGE = timedelta(days=90)


@dataclass(frozen=True)
class Criterion:
    key: str
    title: str
    applies_when: str
    applies: Callable[[dict], bool]
    check: Callable[[dict, date], tuple[str, str, str]]
    structured: dict[str, tuple[str, str]] = field(default_factory=dict)
    extracted: tuple[str, ...] = ()
    document: str | None = None


def check_crm_record(inputs, as_of):
    absent = [name for name, value in inputs.items() if value in (None, "")]
    if absent:
        return EXCEPTION, "missing", "CRM record lacks " + ", ".join(absent)
    return SATISFIED, "", "CRM record has applicant, ABN, asset and loan amount"


def check_credit_report(inputs, as_of):
    if not inputs["report_date"]:
        return EXCEPTION, "missing", "no credit report in the CRM"
    dated = date.fromisoformat(inputs["report_date"])
    if as_of - dated > CREDIT_REPORT_MAX_AGE:
        return EXCEPTION, "expired", f"credit report dated {dated} is older than 90 days"
    return SATISFIED, "", f"credit report dated {dated}, within 90 days"


def check_licence(inputs, as_of):
    expiry = date.fromisoformat(inputs["expiry_date"][0])
    if expiry < as_of:
        return EXCEPTION, "expired", f"licence expired on {expiry}"
    return SATISFIED, "", f"licence valid until {expiry}"


def check_invoice(inputs, as_of):
    invoice, crm = float(inputs["invoice_total"][0]), float(inputs["loan_amount"])
    if invoice != crm:
        return EXCEPTION, "inconsistent", f"invoice total ${invoice:,.0f} differs from CRM loan amount ${crm:,.0f}"
    return SATISFIED, "", f"invoice total matches CRM loan amount ${crm:,.0f}"


def check_financials(inputs, as_of):
    years = sorted(set(inputs["financial_year"]))
    if len(years) < 2:
        return EXCEPTION, "missing", f"only {', '.join(years)} supplied; two years of financials are required"
    return SATISFIED, "", f"financials supplied for {', '.join(years)}"


def check_bank_statements(inputs, as_of):
    months = int(inputs["months_covered"][0])
    if months < 3:
        return EXCEPTION, "missing", f"statements cover {months} months; three are required"
    return SATISFIED, "", f"statements cover {months} months"


def amount(record):
    return record.get("loan_amount") or 0


CRITERIA = [
    Criterion("crm_record@1", "CRM application record", "every application", lambda r: True, check_crm_record,
              structured={name: ("crm/record.json", name) for name in ("applicant", "abn", "asset", "loan_amount")}),
    Criterion("credit_report@1", "Credit report", "every application", lambda r: True, check_credit_report,
              structured={"report_date": ("crm/credit-report.json", "report_date")}),
    Criterion("drivers_licence@1", "Director's driver's licence", "every application", lambda r: True,
              check_licence, extracted=("expiry_date",), document="drivers-licence"),
    Criterion("dealer_invoice@1", "Dealer invoice for the asset", "every equipment loan", lambda r: True,
              check_invoice, structured={"loan_amount": ("crm/record.json", "loan_amount")},
              extracted=("invoice_total",), document="dealer-invoice"),
    Criterion("financials_two_years@1", "Two years of financial statements",
              f"loan amount over ${FINANCIALS_THRESHOLD:,}", lambda r: amount(r) > FINANCIALS_THRESHOLD,
              check_financials, extracted=("financial_year",), document="financials"),
    Criterion("bank_statements@1", "Three months of business bank statements",
              f"loan amount ${FINANCIALS_THRESHOLD:,} or less", lambda r: amount(r) <= FINANCIALS_THRESHOLD,
              check_bank_statements, extracted=("months_covered",), document="bank-statement"),
]

EXTRACTED_INPUTS = {
    "expiry_date": "the licence expiry date, as YYYY-MM-DD",
    "invoice_total": "the invoice total including GST, as a plain number",
    "financial_year": "the financial year each financial statement covers, as FY2025 and the like (one entry per statement)",
    "months_covered": "how many months the bank statements cover, as a whole number",
}


def applicable(record: dict) -> list[Criterion]:
    return [c for c in CRITERIA if c.applies(record)]
