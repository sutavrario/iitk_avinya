"""Document ingestion: parse uploaded files into reviewable, normalized invoice records.

Pure functions live here (no Firestore). Orchestration (jobs, review, confirm) is in
`app/services/ingestion_jobs.py` and `app/services/ingestion_review.py`.
"""
