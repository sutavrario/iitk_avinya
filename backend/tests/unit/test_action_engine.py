import pytest
from datetime import date
from app.services.action_engine import extract_facts

def test_extract_facts_overdue_invoice():
    today = date(2023, 10, 15)
    invoices = [
        {
            "id": "inv_1",
            "invoiceNumber": "INV-001",
            "customerName": "Acme Corp",
            "amountPaise": 500000,
            "dueDate": "2023-10-01", # 14 days overdue
            "status": "unpaid",
        },
        {
            "id": "inv_2",
            "invoiceNumber": "INV-002",
            "customerName": "Beta Ltd",
            "amountPaise": 200000,
            "dueDate": "2023-10-10", # 5 days overdue (not > 7)
            "status": "unpaid",
        },
        {
            "id": "inv_3",
            "invoiceNumber": "INV-003",
            "customerName": "Gamma Inc",
            "amountPaise": 300000,
            "dueDate": "2023-09-01", 
            "status": "paid", # paid, should not be flagged
        }
    ]
    
    facts = extract_facts(invoices, [], today)
    
    # Expecting 1 overdue fact for inv_1
    assert len(facts) == 1
    assert facts[0]["type"] == "overdue"
    assert facts[0]["record_id"] == "inv_1"
    assert "14 days overdue" in facts[0]["fact"]


def test_extract_facts_upcoming_expense():
    today = date(2023, 10, 15)
    expenses = [
        {
            "id": "exp_1",
            "reference": "EXP-001",
            "supplierName": "Supplier A",
            "amountPaise": 100000,
            "dueDate": "2023-10-20", # 5 days away (within 7 days)
            "status": "unpaid",
        },
        {
            "id": "exp_2",
            "reference": "EXP-002",
            "supplierName": "Supplier B",
            "amountPaise": 200000,
            "dueDate": "2023-10-25", # 10 days away (not <= 7)
            "status": "unpaid",
        },
        {
            "id": "exp_3",
            "reference": "EXP-003",
            "supplierName": "Supplier C",
            "amountPaise": 300000,
            "dueDate": "2023-10-12", # Already past due
            "status": "unpaid",
        }
    ]
    
    facts = extract_facts([], expenses, today)
    
    # Expecting 1 upcoming fact for exp_1
    assert len(facts) == 1
    assert facts[0]["type"] == "upcoming"
    assert facts[0]["record_id"] == "exp_1"
    assert "is due on 2023-10-20" in facts[0]["fact"]


def test_extract_facts_missing_data():
    today = date(2023, 10, 15)
    invoices = [
        {
            "id": "inv_1",
            "invoiceNumber": "INV-001",
            "customerName": "Acme Corp",
            "amountPaise": 500000,
            # missing dueDate
            "status": "unpaid",
        }
    ]
    
    facts = extract_facts(invoices, [], today)
    
    assert len(facts) == 1
    assert facts[0]["type"] == "data_missing"
    assert facts[0]["record_id"] == "inv_1"
    assert "has no due date set" in facts[0]["fact"]


def test_extract_facts_limit_5():
    today = date(2023, 10, 15)
    # create 10 overdue invoices
    invoices = []
    for i in range(10):
        invoices.append({
            "id": f"inv_{i}",
            "invoiceNumber": f"INV-00{i}",
            "customerName": "Acme Corp",
            "amountPaise": 500000,
            "dueDate": "2023-10-01", # 14 days overdue
            "status": "unpaid",
        })
        
    facts = extract_facts(invoices, [], today)
    assert len(facts) == 5 # limited to 5
