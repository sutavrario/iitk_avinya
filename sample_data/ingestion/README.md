# Ingestion samples (fictional data)

Regenerate with `backend/.venv/bin/python sample_data/ingestion/generate_samples.py`.

| File | Tests |
|---|---|
| `sales_register.xlsx` | Clean headers; CGST + SGST summed as tax; "Paid"/"Pending" kept as evidence only; UTR reference |
| `tally_sales_export.xlsx` | Title rows above header, Tally column names, "Grand Total" row skipped, extra "Notes" sheet |
| `legacy_bills.xls` | Old Excel format; dd/mm dates; no subtotal/tax columns (stay null, not 0) |
| `sales_with_problems.csv` | One problem per row: ok · missing total · wrong total · duplicate · missing customer · invalid date (31/02) · due before invoice + "Rs. 500/-" · missing invoice no. |
| `purchase_bills.csv` | Semicolon-delimited supplier bills with a payment reference |
| `unknown_columns.csv` | Meaningless headers → column-mapping step |
| `duplicate_of_register.csv` | Repeats INV-1001 from the register → cross-document duplicate |
| `invoice_digital.pdf` | GST invoice with a text layer (no OCR needed) |
| `invoice_scanned.pdf` | Same invoice as an image-only PDF (OCR) |
| `bill_photo.png` | Slightly rotated/blurred supplier bill (OCR; tests split invoice-number repair) |
| `malformed/` | corrupt xlsx, truncated PDF, password-protected PDF, header-only CSV, ragged CSV |
