import os
import sys
import argparse
import time

from utils import setup_logger, load_config, save_json
from pii_detector import PIIDetector
from anonymizer import PIIAnonymizer
from docx_handler import DOCXRedactor
from evaluator import PIIEvaluator


def parse_args():
    parser = argparse.ArgumentParser(description="Production PII Redaction Tool with Evaluation Report")
    parser.add_argument("input_file", nargs="?", default=None, help="Path to input DOCX file")
    parser.add_argument("output_file", nargs="?", default=None, help="Path to output redacted DOCX file")
    parser.add_argument("--config", default="config.yaml", help="Path to configuration file")
    parser.add_argument("--mapping", default="mapping.json", help="Path to output mapping JSON file")
    parser.add_argument("--eval-report", default="evaluation_report.csv", help="Path to evaluation report CSV")
    parser.add_argument("--metrics", default="metrics.txt", help="Path to metrics summary text file")
    parser.add_argument("--log", default="redaction.log", help="Path to log file")
    parser.add_argument("--skip-eval", action="store_true", help="Skip running evaluation metrics")
    return parser.parse_args()


def main():
    args = parse_args()

    # Load configuration
    config = load_config(args.config)
    defaults = config.get("defaults", {})

    # Determine paths
    input_path = args.input_file or defaults.get("input_docx", "input/Red Herring Prospectus.docx")
    output_path = args.output_file or defaults.get("output_docx", "output/redacted.docx")
    mapping_path = args.mapping or defaults.get("mapping_json", "mapping.json")
    eval_csv_path = args.eval_report or defaults.get("eval_report_csv", "evaluation_report.csv")
    metrics_txt_path = args.metrics or defaults.get("metrics_txt", "metrics.txt")
    log_path = args.log or defaults.get("log_file", "redaction.log")

    # Initialize Logger
    logger = setup_logger(log_path)
    logger.info("=================================================================")
    logger.info("           STARTING PII REDACTION SYSTEM PROCESSING              ")
    logger.info("=================================================================")
    logger.info(f"Input Document: {input_path}")
    logger.info(f"Output Document: {output_path}")

    if not os.path.exists(input_path):
        logger.error(f"Input file not found at: {input_path}")
        sys.exit(1)

    start_time = time.time()

    # 1. Initialize PII Detector & Anonymizer
    logger.info("Initializing PII Detector (spaCy + Presidio + Regex)...")
    detector = PIIDetector(config_path=args.config)

    logger.info("Initializing PII Anonymizer (Faker)...")
    anonymizer = PIIAnonymizer()

    # 2. Redact Document
    redactor = DOCXRedactor(detector=detector, anonymizer=anonymizer)
    summary = redactor.redact_document(input_path=input_path, output_path=output_path)

    # 3. Save Mapping JSON
    mapping_dict = anonymizer.get_mapping_dict()
    save_json(mapping_dict, mapping_path)
    logger.info(f"Saved PII replacement mapping dictionary to: {mapping_path}")

    # Save detailed mapping for auditing
    save_json(anonymizer.get_detailed_mapping(), "mapping_details.json")

    # 4. Run Evaluation
    if not args.skip_eval:
        logger.info("Running evaluation suite against benchmark dataset...")
        evaluator = PIIEvaluator(detector=detector)
        df_summary, report_str = evaluator.evaluate()
        evaluator.save_reports(df_summary, report_str, csv_path=eval_csv_path, txt_path=metrics_txt_path)

        print("\n" + report_str + "\n")

    elapsed_time = time.time() - start_time
    logger.info(f"Processing complete in {elapsed_time:.2f} seconds.")
    logger.info("=================================================================")


if __name__ == "__main__":
    main()
