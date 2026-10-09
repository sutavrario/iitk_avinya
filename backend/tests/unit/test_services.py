from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from pydantic import ValidationError

from app.core.errors import AppError, PayloadTooLargeError, UnsupportedMediaTypeError
from app.repositories.money import from_paise, to_paise
from app.schemas.business import BusinessProfileIn
from app.schemas.records import InvoiceIn, PaymentIn
from app.services.authorization import Role, membership_id, role_allows
from app.services.dashboard import compute_summary, financial_year_start
from app.services.documents import read_limited, safe_display_name, storage_path, validate_upload
from app.services.invoices import effective_status

PROFILE = {
    "businessName": "Sharma Store",
    "industry": "retail",
    "location": {"city": "Pune", "state": "Maharashtra"},
}


class TestSchemas:
    def test_client_cannot_set_server_owned_fields(self) -> None:
        for extra in ({"businessId": "other"}, {"ownerUid": "x"}, {"role": "owner"}):
            with pytest.raises(ValidationError):
                BusinessProfileIn.model_validate({**PROFILE, **extra})
        with pytest.raises(ValidationError):
            InvoiceIn.model_validate(
                {
                    "invoiceNumber": "1",
                    "customerName": "A",
                    "issueDate": "2026-10-01",
                    "dueDate": "2026-10-02",
                    "amount": "10",
                    "businessId": "other",
                }
            )

    def test_profile_normalisation(self) -> None:
        p = BusinessProfileIn.model_validate(
            {**PROFILE, "gstin": " 29abcde1234f1z5 ", "goals": ["grow_sales", "grow_sales"]}
        )
        assert p.gstin == "29ABCDE1234F1Z5"
        assert p.goals == ["grow_sales"]
        assert BusinessProfileIn.model_validate({**PROFILE, "gstin": ""}).gstin is None
        with pytest.raises(ValidationError):
            BusinessProfileIn.model_validate({**PROFILE, "gstin": "BAD"})
        with pytest.raises(ValidationError):
            BusinessProfileIn.model_validate({**PROFILE, "location": {"city": "", "state": "X"}})

    def test_invoice_rules(self) -> None:
        base = {
            "invoiceNumber": "1",
            "customerName": "A",
            "issueDate": "2026-10-01",
            "amount": "100",
        }
        with pytest.raises(ValidationError, match="dueDate"):
            InvoiceIn.model_validate({**base, "dueDate": "2026-09-01"})
        with pytest.raises(ValidationError):
            InvoiceIn.model_validate({**base, "dueDate": "2026-10-02", "status": "overdue"})
        with pytest.raises(ValidationError):
            InvoiceIn.model_validate({**base, "dueDate": "2026-10-02", "amount": "-5"})

    def test_payment_not_in_future(self) -> None:
        with pytest.raises(ValidationError, match="future"):
            PaymentIn.model_validate(
                {
                    "date": "2999-01-01",
                    "partyName": "A",
                    "direction": "paid",
                    "amount": "1",
                    "method": "upi",
                }
            )


def test_money_round_trip() -> None:
    assert to_paise(Decimal("1234.56")) == 123456
    assert to_paise(Decimal("0.005")) == 1
    assert from_paise(123456) == 1234.56


def test_roles() -> None:
    assert role_allows(Role.OWNER, Role.ADMIN)
    assert role_allows(Role.MEMBER, Role.MEMBER)
    assert not role_allows(Role.VIEWER, Role.MEMBER)
    assert not role_allows(Role.MEMBER, Role.ADMIN)
    assert membership_id("biz", "uid") == "biz_uid"


class TestDocuments:
    def test_accepts_valid_files(self) -> None:
        assert validate_upload("sales.csv", b"date,amount\n1,2").file_type.kind == "spreadsheet"
        assert (
            validate_upload("bill.PDF", b"%PDF-1.7 ...").file_type.content_type == "application/pdf"
        )
        assert validate_upload("x.xlsx", b"PK\x03\x04rest").extension == ".xlsx"

    @pytest.mark.parametrize(
        ("name", "content", "error"),
        [
            ("notes.docx", b"PK\x03\x04", UnsupportedMediaTypeError),
            ("script.exe", b"MZ", UnsupportedMediaTypeError),
            ("noext", b"abc", UnsupportedMediaTypeError),
            ("fake.pdf", b"<html>", UnsupportedMediaTypeError),
            ("fake.png", b"GIF89a", UnsupportedMediaTypeError),
            ("binary.csv", b"a,b\x00\x00", UnsupportedMediaTypeError),
            ("empty.csv", b"", AppError),
        ],
    )
    def test_rejects_bad_files(self, name: str, content: bytes, error: type[Exception]) -> None:
        with pytest.raises(error):
            validate_upload(name, content)

    def test_size_limit(self) -> None:
        assert read_limited(BytesIO(b"x" * 10), 10) == b"x" * 10
        with pytest.raises(PayloadTooLargeError):
            read_limited(BytesIO(b"x" * 11), 10)

    def test_filenames_cannot_escape(self) -> None:
        assert safe_display_name("../../etc/passwd") == "passwd"
        assert safe_display_name("C:\\Users\\a\\bill.pdf") == "bill.pdf"
        assert safe_display_name("\x00\x1f..") == "upload"
        assert storage_path("biz", "doc", ".pdf") == "businesses/biz/documents/doc/original.pdf"


class TestDashboard:
    TODAY = date(2026, 10, 9)

    def test_empty(self) -> None:
        s = compute_summary([], [], self.TODAY)
        assert s.has_data is False
        assert s.is_mock is False
        assert s.kpis.total_sales == 0
        assert [m.month for m in s.monthly] == ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]
        assert s.period_label == "FY 2026–27"

    def test_figures(self) -> None:
        inv = [
            # overdue 50 days
            {
                "issueDate": "2026-08-01",
                "dueDate": "2026-08-20",
                "amountPaise": 100_00,
                "status": "unpaid",
                "customerName": "A",
            },
            # paid
            {
                "issueDate": "2026-09-01",
                "dueDate": "2026-09-30",
                "amountPaise": 200_00,
                "status": "paid",
                "customerName": "B",
            },
            # not yet due
            {
                "issueDate": "2026-10-01",
                "dueDate": "2026-10-31",
                "amountPaise": 50_00,
                "status": "unpaid",
                "customerName": "A",
            },
            # previous FY: not in sales, but still outstanding (very overdue)
            {
                "issueDate": "2026-03-01",
                "dueDate": "2026-03-15",
                "amountPaise": 10_00,
                "status": "unpaid",
                "customerName": "C",
            },
        ]
        pay = [
            {"date": "2026-09-05", "direction": "received", "amountPaise": 200_00},
            {"date": "2026-09-06", "direction": "paid", "amountPaise": 30_00},
            {"date": "2026-02-01", "direction": "received", "amountPaise": 999_00},  # previous FY
        ]
        s = compute_summary(inv, pay, self.TODAY)
        assert s.has_data
        assert s.kpis.total_sales == 350
        assert s.kpis.outstanding_receivables == 160
        assert s.kpis.overdue_amount == 110
        assert s.kpis.cash_collected == 200
        aging = {b.bucket: b.amount for b in s.receivables_aging}
        assert aging == {"Not yet due": 50, "1–30 days": 0, "31–60 days": 100, "60+ days": 10}
        assert s.top_customers[0].customer_name == "A"
        assert s.top_customers[0].outstanding == 150
        assert s.top_customers[0].oldest_due_days == 50
        sep = next(m for m in s.monthly if m.month == "Sep")
        assert (sep.sales, sep.expenses) == (200, 30)

    def test_financial_year_boundaries(self) -> None:
        assert financial_year_start(date(2026, 3, 31), "april") == date(2025, 4, 1)
        assert financial_year_start(date(2026, 4, 1), "april") == date(2026, 4, 1)
        assert financial_year_start(date(2026, 3, 31), "january") == date(2026, 1, 1)

    def test_overdue_is_derived(self) -> None:
        assert effective_status("unpaid", date(2026, 1, 1), self.TODAY) == "overdue"
        assert effective_status("paid", date(2026, 1, 1), self.TODAY) == "paid"
        assert effective_status("partially_paid", date(2027, 1, 1), self.TODAY) == "partially_paid"
