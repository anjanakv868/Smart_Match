SMART-Match is an intelligent, end-to-end web application built with Streamlit and powered by Google Gemini AI that automates the process of verifying invoices against purchase orders (POs).

Using OCR (pdfplumber, PyMuPDF, and Tesseract) and AI-driven data extraction, SMART-Match reads both PDF and image documents, extracts key invoice and PO details (like invoice number, date, vendor name, items, and total amount), and then compares them intelligently using fuzzy matching (TheFuzz) to detect discrepancies.

When differences are found, the system generates a natural-language “Agent Summary” using Gemini to explain exactly what doesn’t match (e.g., mismatched vendor name, incorrect total, missing items, etc.).

🚀 Key Features

✅ AI-Powered Data Extraction: Automatically extracts structured data (JSON) from PDF or image invoices and POs using Google Gemini.
✅ Smart Comparison Engine: Detects discrepancies between invoice and PO using fuzzy matching for item descriptions.
✅ Mismatch Summary: Generates a human-readable mismatch explanation using Gemini’s LLM capabilities.
✅ Interactive UI: Built in Streamlit with editable data tables, document previews, and real-time comparison.
✅ Fallback System: If text extraction fails, falls back to image-based AI extraction.
✅ Modern UI Styling: Custom dark theme and responsive sidebar for easy navigation.

🧩 Tech Stack

Frontend: Streamlit (custom CSS and responsive layout)

Backend: Python

AI Model: Google Gemini (via google-generativeai)

OCR Libraries: pdfplumber, PyMuPDF (fitz), Pillow

Matching Engine: FuzzyWuzzy (thefuzz)

Environment Management: dotenv
