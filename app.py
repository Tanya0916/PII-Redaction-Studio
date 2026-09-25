import os
import io
import time
import json
import pandas as pd
import streamlit as st
from docx import Document

from utils import load_config
from pii_detector import PIIDetector
from anonymizer import PIIAnonymizer
from docx_handler import DOCXRedactor
from evaluator import PIIEvaluator

# Page setup
st.set_page_config(
    page_title="PII Shield - Redaction & Evaluation Studio",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #2563EB 0%, #7C3AED 50%, #EC4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    
    .sub-title {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.8rem;
    }
    
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(226, 232, 240, 0.2);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .stDownloadButton button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Loading PII Neural Detection Engine...")
def get_detector():
    return PIIDetector(config_path="config.yaml")


def main():
    st.markdown('<div class="main-title">🛡️ PII Redaction & Anonymization Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Enterprise layout-preserving PII redaction, synthetic entity replacement & live evaluation</div>', unsafe_allow_html=True)

    detector = get_detector()

    # Sidebar Controls
    with st.sidebar:
        st.header("⚙️ Configuration")
        st.markdown("---")
        mode = st.radio("Navigation", ["📄 Document Redaction", "📊 Benchmark Evaluation", "🔍 Live Text Inspector", "ℹ️ System Info"])
        
        st.markdown("---")
        st.markdown("### 🎯 Detection Coverage")
        st.markdown("""
        - 👤 **Names (PERSON)**
        - 🏢 **Companies (ORGANIZATION)**
        - 📧 **Emails**
        - 📞 **Phone Numbers**
        - 🎂 **Dates of Birth**
        - 📍 **Addresses & Locations**
        - 💳 **Credit Card Numbers**
        - 🏦 **Bank Account Numbers**
        - 🆔 **SSN, PAN, Aadhaar**
        - 🌐 **IPv4 & IPv6 Addresses**
        """)

    if mode == "📄 Document Redaction":
        st.subheader("📁 Upload DOCX Document for Redaction")
        col_up, col_info = st.columns([2, 1])

        with col_up:
            uploaded_file = st.file_uploader("Choose a .docx document", type=["docx"])
            
            # Default prospectus quick-load button
            default_prospectus_path = "input/Red Herring Prospectus.docx"
            use_sample = False
            if os.path.exists(default_prospectus_path):
                if st.button("⚡ Or Load Included 'Red Herring Prospectus.docx' (1.8MB)"):
                    use_sample = True

        with col_info:
            st.info("💡 **Preservation Guarantee**\nRedaction maintains paragraph formatting, bold/italic styles, table cell structures, and headers/footers.")

        target_bytes = None
        target_name = ""

        if uploaded_file is not None:
            target_bytes = uploaded_file.read()
            target_name = uploaded_file.name
        elif use_sample:
            with open(default_prospectus_path, "rb") as f:
                target_bytes = f.read()
            target_name = "Red Herring Prospectus.docx"

        if target_bytes:
            st.success(f"Loaded: **{target_name}** ({len(target_bytes) / 1024:.1f} KB)")
            
            if st.button("🚀 Run Redaction Pipeline", type="primary"):
                os.makedirs("temp", exist_ok=True)
                temp_in = os.path.join("temp", f"input_{int(time.time())}.docx")
                temp_out = os.path.join("temp", f"redacted_{int(time.time())}.docx")

                with open(temp_in, "wb") as f:
                    f.write(target_bytes)

                anonymizer = PIIAnonymizer()
                redactor = DOCXRedactor(detector=detector, anonymizer=anonymizer)

                with st.spinner("Executing hybrid NER + Presidio + Regex Redaction..."):
                    t0 = time.time()
                    summary = redactor.redact_document(temp_in, temp_out)
                    elapsed = time.time() - t0

                st.balloons()
                st.success(f"Document successfully redacted in {elapsed:.2f} seconds!")

                # Metrics row
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Replacements", summary.get("total_replacements", 0))
                m2.metric("Unique Entities Mapped", len(anonymizer.get_mapping_dict()))
                m3.metric("Processing Time", f"{elapsed:.1f}s")
                m4.metric("Status", "Preserved & Safe")

                # Downloads
                st.markdown("### 📥 Download Outputs")
                d_col1, d_col2, d_col3 = st.columns(3)

                with open(temp_out, "rb") as f:
                    redacted_bytes = f.read()

                mapping_data = anonymizer.get_mapping_dict()
                mapping_json_str = json.dumps(mapping_data, indent=2)
                detailed_json_str = json.dumps(anonymizer.get_detailed_mapping(), indent=2)

                d_col1.download_button(
                    label="📄 Download Redacted DOCX",
                    data=redacted_bytes,
                    file_name=f"redacted_{target_name}",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="dl_docx"
                )

                d_col2.download_button(
                    label="🗺️ Download Mapping (JSON)",
                    data=mapping_json_str,
                    file_name="mapping.json",
                    mime="application/json",
                    key="dl_map"
                )

                d_col3.download_button(
                    label="📊 Download Detailed Audit Log",
                    data=detailed_json_str,
                    file_name="mapping_details.json",
                    mime="application/json",
                    key="dl_audit"
                )

                # Entity Replacement Preview
                st.markdown("---")
                st.markdown("### 🔍 Sample Redaction Mappings")
                if mapping_data:
                    preview_items = list(mapping_data.items())[:20]
                    preview_df = pd.DataFrame(preview_items, columns=["Original PII Detected", "Synthetic Fake Replacement"])
                    st.dataframe(preview_df, use_container_width=True)
                else:
                    st.write("No PII detected in this snippet.")

    elif mode == "📊 Benchmark Evaluation":
        st.subheader("📊 Ground-Truth Evaluation Suite")
        st.markdown("Evaluation metrics computed on representative multi-entity ground-truth annotations across all 12 target PII classes.")

        if os.path.exists("evaluation_report.csv"):
            df_eval = pd.read_csv("evaluation_report.csv")
            
            c1, c2, c3 = st.columns(3)
            overall_row = df_eval[df_eval["Entity"] == "OVERALL"]
            if not overall_row.empty:
                c1.metric("Overall Precision", overall_row["Precision"].values[0])
                c2.metric("Overall Recall", overall_row["Recall"].values[0])
                c3.metric("Overall F1-Score", overall_row["F1-Score"].values[0])
            
            st.dataframe(df_eval, use_container_width=True)

        if st.button("🔄 Re-run Evaluation Suite"):
            with st.spinner("Evaluating ground-truth test suite..."):
                evaluator = PIIEvaluator(detector=detector)
                df_summary, report_str = evaluator.evaluate()
                evaluator.save_reports(df_summary, report_str, "evaluation_report.csv", "metrics.txt")
            st.success("Evaluation complete!")
            st.dataframe(df_summary, use_container_width=True)

        if os.path.exists("metrics.txt"):
            with open("metrics.txt", "r") as f:
                st.text(f.read())

    elif mode == "🔍 Live Text Inspector":
        st.subheader("🔍 Interactive Text PII Scanner")
        sample_text = (
            "Mr. Rajiv Sharma (DOB: 15/08/1982) lives at 45 MG Road, Bangalore 560001. "
            "His email is rajiv.sharma@techcorp.in and mobile is +91 9876543210. "
            "His PAN number is ABCDE1234F and Aadhaar is 5432 1098 7654. "
            "He paid using credit card 4532-1234-5678-9012 and contacted support from IP 192.168.1.105."
        )
        user_input = st.text_area("Input Text snippet:", value=sample_text, height=140)

        if st.button("Inspect & Anonymize Text", type="primary"):
            entities = detector.detect(user_input)
            st.markdown(f"**Found {len(entities)} PII Entities:**")

            if entities:
                ent_df = pd.DataFrame(entities)
                st.dataframe(ent_df[["text", "entity_type", "confidence", "source", "start", "end"]], use_container_width=True)

                anonymizer = PIIAnonymizer()
                redacted_text = user_input
                # Sort descending by start
                for ent in sorted(entities, key=lambda x: x["start"], reverse=True):
                    fake_val = anonymizer.anonymize(ent["text"], ent["entity_type"])
                    redacted_text = redacted_text[:ent["start"]] + fake_val + redacted_text[ent["end"]:]

                st.markdown("#### Anonymized Output:")
                st.code(redacted_text, language="markdown")
            else:
                st.info("No PII found in text.")

    elif mode == "ℹ️ System Info":
        st.subheader("ℹ️ System Architecture & Specs")
        st.markdown("""
        ### Pipeline Specifications:
        - **Core Models**: spaCy `en_core_web_sm` + Microsoft Presidio Analyzer + Regex Engine
        - **Synthetic Generator**: Faker (consistent stateful entity mapping)
        - **DOCX Parser**: python-docx (run-level XML replacement preserving styling)
        - **Supported Classes**: PERSON, ORGANIZATION, EMAIL, PHONE, DATE_OF_BIRTH, LOCATION, CREDIT_CARD, BANK_ACCOUNT, SSN, PAN, AADHAAR, IP_ADDRESS
        - **Output Artifacts**: Redacted DOCX, Mapping JSON, Evaluation CSV, Metrics Summary
        """)


if __name__ == "__main__":
    main()
