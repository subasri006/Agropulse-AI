import os
import streamlit as st
from PIL import Image
import base64
import requests
from io import BytesIO
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import re
import tempfile
from dotenv import load_dotenv

# 🔐 Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("❌ GEMINI_API_KEY not found. Add it to your .env file.")
    st.stop()

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
)

# Convert image to base64
def image_to_base64(image):
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

# Gemini API call
def get_gemini_prediction(base64_image):
    headers = {"Content-Type": "application/json"}
    prompt = """
You are an expert plant pathologist. A leaf image is uploaded. 
Identify the disease (if any) and list exactly 3 short, specific cures.

Return strictly in this format:

Disease: <name>
Cure:
1. <first cure>
2. <second cure>
3. <third cure>
"""
    request_body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(GEMINI_API_URL, headers=headers, json=request_body)
        result = response.json()

        if "candidates" not in result:
            if "error" in result:
                return f"❌ Gemini API Error: {result['error'].get('message', 'Unknown error')}"
            return "❌ Gemini API returned no candidates. Check your API key or request."

        return result["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
        return f"❌ Exception occurred: {str(e)}"

# Extract disease and cures
def extract_disease_and_cure(text):
    disease_match = re.search(r'(?:\*\*?)?Disease(?:\*\*?)?:\s*(.+)', text, re.IGNORECASE)
    cure_matches = re.findall(r'\d+\.\s*(.+)', text)

    disease = disease_match.group(1).strip() if disease_match else "Not found"
    cure = "\n".join([f"{i+1}. {c.strip()}" for i, c in enumerate(cure_matches)]) if cure_matches else "Not found"
    return disease, cure

# Generate PDF
def generate_pdf(disease, cure, image):
    try:
        pdf = FPDF()
        pdf.add_page()

        # Title
        pdf.set_font("helvetica", "B", 14)
        pdf.cell(0, 10, "AgroPulse AI - Plant Diagnosis Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            image.save(tmp.name)
            image_path = tmp.name

        # Insert image
        pdf.ln(5)
        pdf.image(image_path, w=100)

        # Disease
        pdf.ln(10)
        pdf.set_font("helvetica", "B", 12)
        pdf.set_text_color(220, 50, 50)
        pdf.cell(0, 10, f"Disease: {disease}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Cure
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("helvetica", "I", 12)
        pdf.multi_cell(0, 10, f"Cure:\n{cure}")

        os.remove(image_path)

        pdf_output = pdf.output()
        if isinstance(pdf_output, str):
            pdf_output = pdf_output.encode("latin-1")
        return BytesIO(pdf_output)

    except Exception as e:
        st.error(f"❌ PDF generation failed: {e}")
        return None

# 🌿 Streamlit UI
st.set_page_config(page_title="AgroPulse AI", page_icon="🌿")
st.title("🌿 AgroPulse AI - Plant Disease Detector")
st.markdown("Upload a leaf image to get the **plant disease** and its **suggested cures** using AI.")

uploaded_file = st.file_uploader("📷 Choose a plant leaf image...", type=["jpg", "jpeg", "png"])
show_image = st.toggle("👁️ Show Uploaded Image", value=False)

if uploaded_file:
    image = Image.open(uploaded_file)
    if show_image:
        st.image(image, caption="🖼️ Uploaded Image", use_container_width=True)

    with st.spinner("🔍 Analyzing with AI..."):
        base64_img = image_to_base64(image)
        result_text = get_gemini_prediction(base64_img)

    # Extract & Display
    disease, cure = extract_disease_and_cure(result_text)

    st.subheader("🧪 Diagnosis Result")
    st.markdown(f"""
    <div style="border: 1px solid #ccc; border-radius: 6px; padding: 10px;">
        <b>🌿 Plant Disease:</b> {disease}  
        <br><br>
        <b>💊 Suggested Cure:</b><br>
        {"<br>".join(cure.splitlines())}
    </div>
    """, unsafe_allow_html=True)

    pdf_data = generate_pdf(disease, cure, image)
    if pdf_data:
        st.download_button(
            label="📄 Download Diagnosis Report (PDF)",
            data=pdf_data,
            file_name="plant_diagnosis_report.pdf",
            mime="application/pdf"
        )
