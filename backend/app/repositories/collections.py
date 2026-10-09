"""Firestore collection names. See docs/DATA_MODEL.md."""

USERS = "users"
BUSINESSES = "businesses"
BUSINESS_MEMBERS = "businessMembers"

# Business-owned collections: every document has a `businessId` field.
INVOICES = "invoices"
PAYMENTS = "payments"
CUSTOMERS = "customers"
SUPPLIERS = "suppliers"
EXPENSES = "expenses"
UPLOADED_DOCUMENTS = "uploadedDocuments"
CONVERSATIONS = "conversations"
CONVERSATION_MESSAGES = "messages"  # subcollection of conversations
ACTION_PLANS = "actionPlans"
INGESTION_JOBS = "ingestionJobs"  # doc ID = uploadedDocuments ID
EXTRACTED_RECORDS = "extractedRecords"  # subcollection of uploadedDocuments

BUSINESS_OWNED = frozenset(
    {
        INVOICES,
        PAYMENTS,
        CUSTOMERS,
        SUPPLIERS,
        EXPENSES,
        UPLOADED_DOCUMENTS,
        CONVERSATIONS,
        ACTION_PLANS,
    }
)
