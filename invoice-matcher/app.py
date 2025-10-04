import os
import fitz # PyMuPDF
import pdfplumber
import io
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import json
import streamlit as st
from thefuzz import fuzz

# --- Configuration ---
load_dotenv()

# Load API key from environment variables
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    st.error("FATAL: GOOGLE_API_KEY environment variable not set. Please set it to your Gemini API key.")
    st.stop()

# --- Prompts ---
TEXT_PROMPT = """
You are an expert accounts payable specialist. Your task is to analyze the following text content from an invoice and a purchase order and extract key information.

From the INVOICE text, extract:
- Invoice Number
- Date
- Vendor Name
- A list of all line items. Each item should have a 'description', 'quantity', and 'price'.
- Total Amount

From the PURCHASE ORDER text, extract:
- PO Number
- Date
- Vendor Name
- A list of all ordered items. Each item should have a 'description', 'quantity', and 'price'.
- Total Amount

Return your findings ONLY as a single, minified JSON object. The JSON structure must be:
{
  "invoice_data": {
    "invoice_no": "...", "date": "...", "vendor": "...",
    "items": [{"description": "...", "quantity": 1, "price": 0.00}],
    "total": 0.00
  },
  "po_data": {
    "po_no": "...", "date": "...", "vendor": "...",
    "items": [{"description": "...", "quantity": 1, "price": 0.00}],
    "total": 0.00
  }
}
"""

IMAGE_PROMPT = """
You are an expert accounts payable specialist. Your task is to extract key information from the provided document images.

From the INVOICE image, extract:
- Invoice Number
- Date
- Vendor Name
- A list of all line items. Each item should have a 'description', 'quantity', and 'price'.
- Total Amount

From the PURCHASE ORDER image, extract:
- PO Number
- Date
- Vendor Name
- A list of all ordered items. Each item should have a 'description', 'quantity', and 'price'.
- Total Amount

Return your findings ONLY as a single, minified JSON object. The JSON structure must be:
{
  "invoice_data": {
    "invoice_no": "...", "date": "...", "vendor": "...",
    "items": [{"description": "...", "quantity": 1, "price": 0.00}],
    "total": 0.00
  },
  "po_data": {
    "po_no": "...", "date": "...", "vendor": "...",
    "items": [{"description": "...", "quantity": 1, "price": 0.00}],
    "total": 0.00
  }
}
"""

# Prompt for generating a mismatch summary using Gemini
MISMATCH_SUMMARY_PROMPT = """\nYou are an accounts payable specialist providing a summary of the discrepancies between an invoice and a purchase order. Based on the following data, provide a brief, easy-to-understand summary of the key mismatches. Focus on the vendor, total amount, and any line item issues.\n\n**Invoice Data:**\n{invoice_data}\n\n**Purchase Order Data:**\n{po_data}\n\n**Mismatch Details:**\n{mismatch_details}\n\n**Example Summary:**\n"There are a few issues with this invoice. The vendor name doesn't match the purchase order, and the total amount is off by $50. Additionally, one of the line items has a price discrepancy, and another item was on the invoice but not on the original PO."\n"""

# --- Gemini API Interaction ---
def get_gemini_response(payload):
    model = genai.GenerativeModel('gemini-flash-latest')
    try:
        generation_config = genai.types.GenerationConfig(temperature=0)
        response = model.generate_content(payload, generation_config=generation_config)
        json_text = response.text.strip().replace('json', '').replace('', '')
        return json.loads(json_text)
    except Exception as e:
        st.error("An error occurred with the Gemini API or its response.")
        st.write("Raw Gemini response:", response.text if 'response' in locals() else "No response object")
        st.stop()

def get_mismatch_summary_from_gemini(invoice_data, po_data, mismatch_details):
    """
    Generates a mismatch summary using the Gemini API.

    Args:
        invoice_data: The extracted invoice data.
        po_data: The extracted purchase order data.
        mismatch_details: A dictionary containing the details of the mismatches.

    Returns:
        A string containing the generated mismatch summary.
    """
    model = genai.GenerativeModel('gemini-flash-latest')
    prompt = MISMATCH_SUMMARY_PROMPT.format(
        invoice_data=json.dumps(invoice_data, indent=2),
        po_data=json.dumps(po_data, indent=2),
        mismatch_details=json.dumps(mismatch_details, indent=2)
    )
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Failed to generate mismatch summary: {e}")
        return "Could not generate summary."

# --- Helpers ---
def get_text_with_pdfplumber(file):
    """
    Extracts text from a PDF file using pdfplumber.

    Args:
        file: The PDF file to extract text from.

    Returns:
        A string containing the extracted text.
    """
    try:
        with pdfplumber.open(file) as pdf:
            text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        return text.strip()
    except Exception as e:
        print(f"pdfplumber failed: {e}")
        return ""

def prepare_image(file):
    if not file.name.lower().endswith('.pdf'):
        return Image.open(file)
    try:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=300)
        img_data = pix.tobytes("png")
        doc.close()
        return Image.open(io.BytesIO(img_data))
    except Exception as e:
        st.error(f"Failed to convert PDF to image: {e}")
        st.stop()

def editable_display_doc(title, data, doc_type):
    """
    Displays an editable form for a document.

    Args:
        title: The title of the form.
        data: The data to display in the form.
        doc_type: The type of the document (e.g., "invoice", "po").

    Returns:
        The edited data.
    """
    with st.container():
        st.subheader(title)
        data[f'{doc_type.lower()}_no'] = st.text_input(f"{doc_type.capitalize()} Number", value=data.get(f'{doc_type.lower()}_no', 'N/A'), key=f"{doc_type}_no")
        data['vendor'] = st.text_input("Vendor", value=data.get('vendor', 'N/A'), key=f"{doc_type}_vendor")
        data['total'] = st.number_input("Total Amount", value=float(data.get('total', 0.0)), key=f"{doc_type}_total")
        
        with st.expander("View Itemized Details"):
            items = data.get("items", [])
            if items:
                edited_items = st.data_editor(items, key=f"{doc_type}_items")
                data['items'] = edited_items
            else:
                st.info("No items found.")
    return data

def get_match_summary(invoice, po):
    """
    Compares an invoice and a purchase order and returns a summary of the match.

    Args:
        invoice: The invoice data.
        po: The purchase order data.

    Returns:
        A dictionary containing the match summary.
    """
    summary = {
        'vendor_match': invoice.get('vendor') == po.get('vendor'),
        'total_match': abs(float(invoice.get('total', 0.0)) - float(po.get('total', 0.0))) < 0.01,
        'matching_items': [],
        'discrepancy_items': [],
        'invoice_only_items': [],
        'po_only_items': list(po.get('items', []))
    }

    invoice_items = list(invoice.get('items', []))

    for inv_item in invoice_items[:]:
        found_match = False
        for po_item in summary['po_only_items'][:]:
            # Use fuzzy matching for descriptions
            if fuzz.ratio(inv_item.get('description', '').lower(), po_item.get('description', '').lower()) > 80:
                if inv_item.get('quantity') == po_item.get('quantity') and abs(float(inv_item.get('price', 0.0)) - float(po_item.get('price', 0.0))) < 0.01:
                    summary['matching_items'].append(inv_item)
                else:
                    summary['discrepancy_items'].append({'invoice': inv_item, 'po': po_item})
                summary['po_only_items'].remove(po_item)
                invoice_items.remove(inv_item)
                found_match = True
                break
        if not found_match:
            summary['invoice_only_items'].append(inv_item)
            
    return summary

# --- Streamlit UI ---
st.set_page_config(page_title="SMART-Match", layout="wide")

# --- STYLE ---
def load_css():
    """
    Loads custom CSS for the Streamlit app.
    """
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');
        body {
            font-family: 'Roboto', sans-serif;
        }
        .stApp {
            background-color: #0e1117;
            background-image: url("https://www.transparenttextures.com/patterns/3d-casio.png");
            color: white;
        }
        .stApp .card {
            background-color: #1e1e1e;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .stApp section[data-testid="stSidebar"] {
            background-color: white !important;
            color: black;
        }
        .stApp .stMetric label, .stApp .stMetric div {
            color: white;
        }
        .stApp .stButton > button {
            background-color: #4CAF50;
            color: white;
            padding: 12px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            box-shadow: 0 5px #999;
            transition: all 0.1s ease-in-out;
        }
        .stApp .stButton > button:hover {
            background-color: #45a049;
        }
        .stApp .stButton > button:active {
            background-color: #45a049;
            box-shadow: 0 2px #666;
            transform: translateY(4px);
        }
        .stApp .stDownloadButton > button {
            background-color: #4CAF50;
            color: white;
        }
        .stFileUploader label {
            color: black !important;
        }
        .st-emotion-cache-1vzeuhh {
            color: black !important;
        }
        [data-testid="stToolbar"] button {
            color: white !important;
        }
    </style>
    """, unsafe_allow_html=True)

load_css()

# --- SIDEBAR ---
def clear_session_state():
    st.session_state.invoice_uploader = None
    st.session_state.po_uploader = None
    # Clear any other session state variables if necessary
    for key in st.session_state.keys():
        if 'data' in key:
            del st.session_state[key]

with st.sidebar:
    st.title("Invoice Matcher")
    st.write("Upload an invoice and its corresponding purchase order to automatically compare them.")
    
    invoice_file = st.file_uploader(" Upload Invoice", type=["pdf", "png", "jpg", "jpeg"], key="invoice_uploader")
    po_file = st.file_uploader(" Upload Purchase Order", type=["pdf", "png", "jpg", "jpeg"], key="po_uploader")

    col1, col2 = st.columns(2)
    with col1:
        compare_button = st.button("View Matching", use_container_width=True, help="Compare the uploaded invoice and purchase order")
    with col2:
        clear_button = st.button("Clear", use_container_width=True, help="Clear the uploaded files and reset the application", on_click=clear_session_state)

# --- MAIN APP ---
st.title("SMART-Match: AI-Powered Invoice & PO Reconciliation")

st.info("""
**Welcome to SMART-Match!**

This tool helps you quickly compare invoices and purchase orders.

**How to get started:**

1.  **Upload your invoice** using the uploader in the sidebar.
2.  **Upload your purchase order** using the uploader in the sidebar.
3.  **Click the "View Matching" button** to start the analysis.

The results will show you a summary of the match, and you can view the details of each document in the tabs.
""")

st.divider()

if compare_button:
    if invoice_file is None or po_file is None:
        st.error("Please upload both an Invoice and a Purchase Order file.")
        st.stop()

    with st.spinner("🤖 Analyzing documents..."):
        # --- Document Analysis ---
        invoice_text = get_text_with_pdfplumber(invoice_file)
        po_text = get_text_with_pdfplumber(po_file)

        # Reset file pointers
        invoice_file.seek(0)
        po_file.seek(0)

        if invoice_text and po_text:
            st.info("✅ Using text-based extraction.")
            payload = [TEXT_PROMPT, f"\n--- INVOICE TEXT ---\n{invoice_text}", f"\n--- PO TEXT ---\n{po_text}"]
            analysis = get_gemini_response(payload)
        else:
            st.warning("⚠ Text extraction failed. Falling back to image-based analysis.")
            invoice_image = prepare_image(invoice_file)
            po_image = prepare_image(po_file)
            payload = [IMAGE_PROMPT, invoice_image, po_image]
            analysis = get_gemini_response(payload)

    st.success("Analysis complete!")

    if not analysis:
        st.error("The analysis could not be completed. Please check the Gemini API key and the document files.")
        st.stop()

    invoice_data = analysis.get('invoice_data', {})
    po_data = analysis.get('po_data', {})

    if 'invoice_data' not in st.session_state:
        st.session_state.invoice_data = invoice_data
    if 'po_data' not in st.session_state:
        st.session_state.po_data = po_data

    # --- Results Tabs ---
    st.subheader("📋 Analysis Results")
    tab1, tab2, tab3 = st.tabs(["✅ Match Summary", "📄 Invoice", "📑 Purchase Order"])

    with tab1:
        summary = get_match_summary(st.session_state.invoice_data, st.session_state.po_data)

        # --- High-Level Status ---
        st.subheader("Match Status")
        if summary['vendor_match'] and summary['total_match'] and not summary['discrepancy_items'] and not summary['invoice_only_items'] and not summary['po_only_items']:
            st.success("✅ Full Match")
        elif summary['vendor_match'] and summary['total_match']:
            st.warning("🔶 Partial Match (Line Item Discrepancies)")
        else:
            st.error("❌ Mismatch")

        # --- Detailed Breakdown ---
        st.subheader("Detailed Breakdown")
        st.metric("Vendor Match", "✅" if summary['vendor_match'] else "❌")
        st.metric("Total Amount Match", "✅" if summary['total_match'] else "❌")

        # --- Agent-Style Summary ---
        st.subheader("Agent-Style Summary")
        is_mismatch = not summary['vendor_match'] or not summary['total_match'] or summary['discrepancy_items'] or summary['invoice_only_items'] or summary['po_only_items']
        if is_mismatch:
            with st.spinner("🕵️‍♀️ Generating agent summary..."):
                agent_summary = get_mismatch_summary_from_gemini(st.session_state.invoice_data, st.session_state.po_data, summary)
                st.info(agent_summary)
        else:
            st.success("Everything looks good! No discrepancies found.")

    with tab2:
        with st.container():
            st.session_state.edited_invoice_data = editable_display_doc("📄 Invoice Details", st.session_state.invoice_data, "invoice")

    with tab3:
        with st.container():
            st.session_state.edited_po_data = editable_display_doc("📑 Purchase Order Details", st.session_state.po_data, "po")
            
    st.divider()
    
    # --- Document Preview ---
    st.subheader("📄 Document Preview")
    doc_preview_tabs = st.tabs(["Invoice", "Purchase Order"])
    with doc_preview_tabs[0]:
        st.image(prepare_image(invoice_file), use_container_width=True)
    with doc_preview_tabs[1]:
        st.image(prepare_image(po_file), use_container_width=True)
