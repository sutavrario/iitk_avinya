"""Action engine for generating the weekly business action plan."""

import json
from datetime import date, timedelta
from typing import Any

from app.schemas.dashboard import ActionItem
from app.services.llm_providers import get_chat_provider

def _build_llm_prompt(facts: list[dict[str, Any]]) -> str:
    return f"""You are VyaparAI, an expert business assistant.
Below are several confirmed facts derived deterministically from the user's business records.
Your job is to generate a prioritized action plan based ONLY on these facts.

RULES:
1. Distinguish confirmed facts from your own recommendations.
2. Do not hallucinate or invent new data. 
3. Return ONLY a JSON array of action items matching the exact JSON schema.
4. If an expense anomaly is found, provide a realistic but concise reason based on the context.

FACTS:
{json.dumps(facts, indent=2)}

SCHEMA for each action item:
{{
  "id": "unique-id-string",
  "type": "overdue" | "upcoming" | "data_missing" | "anomaly" | "recommendation",
  "priority": "high" | "medium" | "low",
  "title": "Short title",
  "description": "Longer explanation (your input here)",
  "reason": "The deterministic fact that triggered this",
  "suggested_deadline": "YYYY-MM-DD or null",
  "related_record_ids": ["id1", "id2"],
  "is_fact": true
}}
"""

def extract_facts(invoices: list[dict[str, Any]], expenses: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    facts = []

    # Rule 1: Overdue Invoices (> 7 days)
    for inv in invoices:
        due = date.fromisoformat(inv["dueDate"]) if inv.get("dueDate") else None
        if due and (today - due).days > 7 and inv.get("status") != "paid":
            amount = int(inv.get("amountPaise", 0)) / 100
            facts.append({
                "type": "overdue",
                "fact": f"Invoice {inv.get('invoiceNumber', inv['id'])} to {inv['customerName']} for ₹{amount} is {(today - due).days} days overdue.",
                "record_id": inv["id"],
                "due_date": due.isoformat(),
            })

    # Rule 2: Upcoming obligations (expenses due in next 7 days)
    for exp in expenses:
        due = date.fromisoformat(exp["dueDate"]) if exp.get("dueDate") else None
        if due and 0 <= (due - today).days <= 7 and exp.get("status") != "paid":
            amount = int(exp.get("amountPaise", 0)) / 100
            facts.append({
                "type": "upcoming",
                "fact": f"Expense {exp.get('reference', exp['id'])} to {exp['supplierName']} for ₹{amount} is due on {due.isoformat()}.",
                "record_id": exp["id"],
                "due_date": due.isoformat(),
            })

    # Rule 3: Data Completeness
    for inv in invoices:
        if not inv.get("dueDate"):
            facts.append({
                "type": "data_missing",
                "fact": f"Invoice {inv.get('invoiceNumber', inv['id'])} has no due date set.",
                "record_id": inv["id"],
            })

    return facts[:5]

def generate_action_plan(
    invoices: list[dict[str, Any]],
    expenses: list[dict[str, Any]],
    today: date,
) -> list[ActionItem]:
    facts = extract_facts(invoices, expenses, today)

    if not facts:
        return []

    try:
        prompt = _build_llm_prompt(facts)
        chat = get_chat_provider()
        response_text = chat.generate(
            prompt=prompt,
            system_instruction="You are a JSON-only API. Respond with a valid JSON array.",
            temperature=0.2,
        )
        
        # Parse the JSON response
        try:
            # Strip markdown block formatting if present
            if response_text.startswith("```json"):
                response_text = response_text[7:-3]
            elif response_text.startswith("```"):
                response_text = response_text[3:-3]
                
            items_data = json.loads(response_text)
            if isinstance(items_data, dict) and "items" in items_data:
                items_data = items_data["items"]
                
            items = []
            for item in items_data:
                # Ensure it maps nicely to ActionItem
                items.append(ActionItem.model_validate(item))
            return items
        except Exception as parse_error:
            print(f"Failed to parse LLM action plan: {parse_error}")
            return []
    except Exception as e:
        print(f"Error generating action plan: {e}")
        return []
