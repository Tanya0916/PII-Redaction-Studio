# Enterprise PII Redaction & Anonymization Tool with Evaluation Report

##  Project Overview
This project is a complete, production-quality Python solution designed to detect and redact **Personally Identifiable Information (PII)** from complex Microsoft Word (`.docx`) documents—specifically tailored for high-density legal and financial documents such as **Red Herring Prospectuses**.

The system replaces sensitive entities with realistic, context-aware fake data using **Faker** while guaranteeing **strict cross-document consistency** (every occurrence of the same original entity maps to the exact same anonymized replacement). Furthermore, it preserves all document styling, table structures, headers, footers, and paragraph formatting without disrupting the layout.

---

##  System Architecture & Workflow

```
┌────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ Input DOCX Document    │ ───► │ Hybrid PII Detector     │ ───► │ Consistent Anonymizer   │
│ (Red Herring Prospect) │      │ (NER + Presidio + Regex)│      │ (Faker Mapping Engine)  │
└────────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
                                                                              │
                                                                              ▼
┌────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ Evaluation Report      │ ◄─── │ Evaluator Engine        │ ◄─── │ DOCX Format Preserver   │
│ (CSV & metrics.txt)    │      │ (Precision/Recall/F1)   │      │ (Run-Level Replacement) │
└────────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
                                                                              │
                                                                              ▼
                                                                 ┌─────────────────────────┐
                                                                 │ Output: redacted.docx   │
                                                                 │ & mapping.json          │
                                                                 └─────────────────────────┘
```

---

##  Key Features & Technical Capabilities

1. **Hybrid PII Detection Engine**:
   - **Named Entity Recognition (NER)**: Powered by **spaCy** (`en_core_web_sm` / `en_core_web_lg`) and **Microsoft Presidio Analyzer** for `PERSON`, `ORGANIZATION`, `LOCATION`.
   - **Custom Regular Expressions**: Optimized for structured PII types including **Emails**, **Phone Numbers** (+91 Indian & International), **IPv4/IPv6 Addresses**, **Credit Cards**, **US SSNs**, **Indian PAN Cards**, **Aadhaar Numbers**, **Bank Account Numbers**, and **Dates of Birth (DOB)**.

2. **Cross-Document Anonymization Consistency**:
   - Utilizes `Faker` to generate contextually relevant fake replacements.
   - Maintains an in-memory mapping index stored to `mapping.json`.
   - *Example*: `John Smith` → `Michael Brown`. Every single instance of `John Smith` throughout body text, tables, headers, and footers will always be replaced by `Michael Brown`.

3. **Layout & Formatting Preservation**:
   - Implements **smart run-level string replacement** in `python-docx`.
   - Preserves character-level formatting (bold, italics, underline, font size, font family, text colors).
   - Processes main body paragraphs, tables (including nested cells), headers, and footers.

4. **Automated Benchmark & Evaluation Suite**:
   - Evaluates system performance against labeled benchmark datasets.
   - Computes **True Positives (TP)**, **False Positives (FP)**, **False Negatives (FN)**, **Precision**, **Recall**, and **F1-Scores** per entity category and overall summary.
   - Exports results directly to `evaluation_report.csv` and formatted `metrics.txt`.

5. **Production Features**:
   - Flexible YAML configuration (`config.yaml`) to enable/disable entity types or tune confidence thresholds.
   - Command-Line Interface (CLI) supporting positional or flagged parameters.
   - Structured logging saved to `redaction.log`.

---

##  Target PII Entities

| PII Category | Entity Type | Detection Strategy | Replacement Strategy |
| :--- | :--- | :--- | :--- |
| **Person** | Full Name | Presidio / spaCy NER | Realistic Fake Name (`Faker.name()`) |
| **Person** | Email Address | Custom Regex / Presidio | Realistic Domain Email (`Faker.email()`) |
| **Person** | Phone Number | Regex (`+91` & local) | Realistic Phone Number |
| **Person** | Date of Birth | Regex / NER / Presidio | Fake Formatted Date |
| **Organization**| Company Name | spaCy NER / Presidio | Realistic Company Name (`Faker.company()`) |
| **Financial** | Credit Card | Regex (13-16 digits) | Valid Fake Card (`Faker.credit_card_number()`) |
| **Financial** | Bank Account | Regex + Context Window | Fake Account Digits |
| **Government** | US SSN | Regex (`XXX-XX-XXXX`) | Realistic SSN (`Faker.ssn()`) |
| **Government** | PAN (India) | Regex (`ABCDE1234F`) | Valid Pattern PAN String |
| **Government** | Aadhaar (India) | Regex (`XXXX XXXX XXXX`) | Valid Pattern 12-Digit Number |
| **Location** | Addresses / Cities | spaCy NER / Presidio | Realistic City / Address |
| **Technical** | IPv4 / IPv6 | Regex | Fake IP Address (`Faker.ipv4()`) |

---

##  Installation & Setup

### Prerequisites
- Python **3.11+**

### Step 1: Install Dependencies
```bash
pip install presidio-analyzer presidio-anonymizer spacy faker python-docx pandas pyyaml
```

### Step 2: Download spaCy Language Models
```bash
python -m spacy download en_core_web_sm
```

---

## Execution & Usage

### 1. Standard Run (Default Input & Output)
```bash
python main.py
```
*Processes `input/Red Herring Prospectus.docx` and generates `output/redacted.docx`, `mapping.json`, `evaluation_report.csv`, and `metrics.txt`.*

### 2. Custom Input/Output CLI Execution
```bash
python main.py input/my_document.docx output/my_redacted.docx
```

### 3. Additional CLI Flags
```bash
python main.py --config config.yaml --mapping mapping.json --eval-report evaluation_report.csv --metrics metrics.txt
```

---

##  Evaluation Results :

Running the evaluation engine against labeled test samples yields the following benchmark results:

```
===============================================================================
                      PII REDACTION EVALUATION REPORT                          
===============================================================================

Entity             | TP   | FP   | FN   | Precision  | Recall     | F1-Score  
-------------------------------------------------------------------------------
PERSON             | 4    | 1    | 0    | 80.00%     | 100.00%    | 88.89%    
ORGANIZATION       | 2    | 0    | 0    | 100.00%    | 100.00%    | 100.00%   
EMAIL              | 3    | 0    | 0    | 100.00%    | 100.00%    | 100.00%   
PHONE              | 2    | 0    | 0    | 100.00%    | 100.00%    | 100.00%   
DATE_OF_BIRTH      | 3    | 1    | 0    | 75.00%     | 100.00%    | 85.71%    
LOCATION           | 3    | 0    | 1    | 100.00%    | 75.00%     | 85.71%    
CREDIT_CARD        | 1    | 0    | 0    | 100.00%    | 100.00%    | 100.00%   
BANK_ACCOUNT       | 1    | 0    | 0    | 100.00%    | 100.00%    | 100.00%   
SSN                | 1    | 0    | 0    | 100.00%    | 100.00%    | 100.00%   
PAN                | 1    | 0    | 0    | 100.00%    | 100.00%    | 100.00%   
AADHAAR            | 1    | 0    | 0    | 100.00%    | 100.00%    | 100.00%   
IP_ADDRESS         | 1    | 0    | 0    | 100.00%    | 100.00%    | 100.00%   
-------------------------------------------------------------------------------
OVERALL            | 23   | 2    | 1    | 92.00%     | 95.83%     | 93.88%    
===============================================================================
Overall Precision: 92.00%
Overall Recall:    95.83%
Overall F1-Score:  93.88%
===============================================================================
```

---

## Strengths & Key Advantages

1. **High Recall with Regex**: Precise regex patterns ensure zero-miss detection for emails, phone numbers, IP addresses, PAN cards, SSNs, and credit cards.
2. **Contextual Name Detection via NER**: Leveraging spaCy and Presidio NER allows capturing full names and corporate entities that regex cannot easily capture.
3. **Robust DOCX Layout Preservation**: Run-level text substitution ensures headers, tables, bold/italic text, and document formatting remain 100% intact.
4. **Strict Cross-Document Consistency**: Guarantees identical original entity strings map to the exact same replacement value across all paragraphs and tables.



## 🌐 Interactive Web UI & Cloud Deployment

The repository includes a modern web interface built with **Streamlit** ([`app.py`](file:///c:/Users/HP/OneDrive/Desktop/ASSIGNMENT/app.py)):

- **Document Redaction**: Drag & drop any `.docx` file or 1-click test with the included *Red Herring Prospectus.docx*.
- **Download Artifacts**: 1-click download for redacted DOCX, `mapping.json`, and audit logs.
- **Live Text Inspector**: Interactive real-time test bench for scanning and anonymizing raw text snippets.
- **Benchmark Evaluation**: Dynamic visualization of the precision, recall, and F1-score evaluation matrix.

### Local Web UI Execution
```bash
streamlit run app.py
```

### 1-Click Deploy to Render / Cloud
1. Push this repository to GitHub.
2. In [Render Dashboard](https://dashboard.render.com/), click **New +** → **Blueprint** (or **Web Service**).
3. Connect your repository. Render automatically reads [`render.yaml`](file:///c:/Users/HP/OneDrive/Desktop/ASSIGNMENT/render.yaml):
   - **Environment**: Python 3.11
   - **Build Command**: `pip install -r requirements.txt && python -m spacy download en_core_web_sm`
   - **Start Command**: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.enableCORS false --server.enableXsrfProtection false`
4. Click **Deploy** to get your public `https://<your-service>.onrender.com` URL.

---

```
project/
│
├── main.py                # Main CLI entry point script
├── pii_detector.py        # Hybrid NER + Presidio + Regex PII detection engine
├── anonymizer.py          # Faker-based consistent fake data generator
├── docx_handler.py        # DOCX layout-preserving redactor module
├── evaluator.py           # Evaluation framework calculating TP/FP/FN/Precision/Recall/F1
├── utils.py               # Logger setup, config reader & overlap resolution
│
├── config.yaml            # YAML configuration for pipeline & PII rules
├── requirements.txt       # Project Python package dependencies
├── README.md              # Project documentation & methodology report
│
├── input/                 # Directory for input DOCX files
│   └── Red Herring Prospectus.docx
│
├── output/                # Directory for generated redacted files
│   └── redacted.docx
│
├── mapping.json           # JSON dictionary mapping original PII -> fake values
├── evaluation_report.csv  # CSV evaluation metrics report
├── metrics.txt            # Formatted human-readable evaluation report
└── redaction.log          # Detailed execution log file
```
