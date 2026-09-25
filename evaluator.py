import os
import csv
import logging
from typing import List, Dict, Any, Tuple
import pandas as pd

from pii_detector import PIIDetector

logger = logging.getLogger("PIIRedactor")


class PIIEvaluator:
    """
    Evaluates PII detection system against a ground truth labeled dataset.
    Calculates True Positives (TP), False Positives (FP), False Negatives (FN),
    Precision, Recall, and F1-score per PII type and overall summary.
    """

    # Comprehensive benchmark dataset representing Red Herring Prospectus PII patterns
    DEFAULT_BENCHMARK_DATASET = [
        {
            "text": "For queries contact Kushal Hegde at cs.connect@kshinternational.com or call +91 9876543210.",
            "ground_truth": [
                {"text": "Kushal Hegde", "type": "PERSON"},
                {"text": "cs.connect@kshinternational.com", "type": "EMAIL"},
                {"text": "+91 9876543210", "type": "PHONE"}
            ]
        },
        {
            "text": "Sarthak Malvadkar can be reached at 022-68052182 or via email at sheetal.parab@nuvama.com.",
            "ground_truth": [
                {"text": "Sarthak Malvadkar", "type": "PERSON"},
                {"text": "022-68052182", "type": "PHONE"},
                {"text": "sheetal.parab@nuvama.com", "type": "EMAIL"}
            ]
        },
        {
            "text": "KSH International Limited was incorporated on July 30, 1979 in Mumbai, Maharashtra.",
            "ground_truth": [
                {"text": "KSH International Limited", "type": "ORGANIZATION"},
                {"text": "July 30, 1979", "type": "DATE_OF_BIRTH"},
                {"text": "Mumbai", "type": "LOCATION"},
                {"text": "Maharashtra", "type": "LOCATION"}
            ]
        },
        {
            "text": "Bhandary Metal Extrusion Private Limited operated from Village Birdewadi, Chakan Taluka - Khed, Pune 410501.",
            "ground_truth": [
                {"text": "Bhandary Metal Extrusion Private Limited", "type": "ORGANIZATION"},
                {"text": "Village Birdewadi", "type": "LOCATION"},
                {"text": "Pune", "type": "LOCATION"}
            ]
        },
        {
            "text": "The lead manager Cherag Gyara submitted PAN ABCDE1234F and SSN 123-45-6789 on 10/12/2025.",
            "ground_truth": [
                {"text": "Cherag Gyara", "type": "PERSON"},
                {"text": "ABCDE1234F", "type": "PAN"},
                {"text": "123-45-6789", "type": "SSN"},
                {"text": "10/12/2025", "type": "DATE_OF_BIRTH"}
            ]
        },
        {
            "text": "Customer payment processed via credit card 4532-1122-3344-5566 and bank account 987654321098.",
            "ground_truth": [
                {"text": "4532-1122-3344-5566", "type": "CREDIT_CARD"},
                {"text": "987654321098", "type": "BANK_ACCOUNT"}
            ]
        },
        {
            "text": "Server IP address logged as 192.168.1.100 and Aadhaar number 4567 8901 2345.",
            "ground_truth": [
                {"text": "192.168.1.100", "type": "IP_ADDRESS"},
                {"text": "4567 8901 2345", "type": "AADHAAR"}
            ]
        },
        {
            "text": "Executive Anand Soni sent confirmation from anand.soni@bajajfinserv.in on December 10, 2025.",
            "ground_truth": [
                {"text": "Anand Soni", "type": "PERSON"},
                {"text": "anand.soni@bajajfinserv.in", "type": "EMAIL"},
                {"text": "December 10, 2025", "type": "DATE_OF_BIRTH"}
            ]
        }
    ]

    def __init__(self, detector: PIIDetector):
        self.detector = detector

    def evaluate(self, dataset: List[Dict[str, Any]] = None) -> Tuple[pd.DataFrame, str]:
        """
        Runs detection over the benchmark dataset and calculates TP, FP, FN,
        Precision, Recall, and F1-score metrics per entity type and overall.
        """
        if dataset is None:
            dataset = self.DEFAULT_BENCHMARK_DATASET

        all_entity_types = [
            "PERSON", "ORGANIZATION", "EMAIL", "PHONE", "DATE_OF_BIRTH",
            "LOCATION", "CREDIT_CARD", "BANK_ACCOUNT", "SSN", "PAN", "AADHAAR", "IP_ADDRESS"
        ]

        stats = {e: {"TP": 0, "FP": 0, "FN": 0} for e in all_entity_types}

        for sample in dataset:
            text = sample["text"]
            ground_truth = sample["ground_truth"]

            # Run detector
            detected = self.detector.detect(text)

            gt_matched = [False] * len(ground_truth)
            det_matched = [False] * len(detected)

            # Match detected against ground truth
            for d_idx, det in enumerate(detected):
                det_text = det["text"].strip().lower()
                det_type = det["entity_type"]

                for g_idx, gt in enumerate(ground_truth):
                    if gt_matched[g_idx]:
                        continue
                    gt_text = gt["text"].strip().lower()
                    gt_type = gt["type"]

                    if (det_text == gt_text or det_text in gt_text or gt_text in det_text) and det_type == gt_type:
                        stats[gt_type]["TP"] += 1
                        gt_matched[g_idx] = True
                        det_matched[d_idx] = True
                        break

            # Unmatched detected entities are FP
            for d_idx, det in enumerate(detected):
                if not det_matched[d_idx]:
                    ent_type = det["entity_type"]
                    if ent_type in stats:
                        stats[ent_type]["FP"] += 1

            # Unmatched ground truth entities are FN
            for g_idx, gt in enumerate(ground_truth):
                if not gt_matched[g_idx]:
                    ent_type = gt["type"]
                    if ent_type in stats:
                        stats[ent_type]["FN"] += 1

        rows = []
        total_tp, total_fp, total_fn = 0, 0, 0

        for ent_type in all_entity_types:
            tp = stats[ent_type]["TP"]
            fp = stats[ent_type]["FP"]
            fn = stats[ent_type]["FN"]

            total_tp += tp
            total_fp += fp
            total_fn += fn

            precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 and tp > 0 else 0.0)
            recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
            if (tp + fp) > 0 and (tp + fn) > 0:
                precision = tp / (tp + fp)
                recall = tp / (tp + fn)
            f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

            rows.append({
                "Entity": ent_type,
                "TP": tp,
                "FP": fp,
                "FN": fn,
                "Precision": round(precision, 4),
                "Recall": round(recall, 4),
                "F1": round(f1, 4)
            })

        overall_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        overall_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        overall_f1 = (2 * overall_prec * overall_rec) / (overall_prec + overall_rec) if (overall_prec + overall_rec) > 0 else 0.0

        summary_row = {
            "Entity": "OVERALL",
            "TP": total_tp,
            "FP": total_fp,
            "FN": total_fn,
            "Precision": round(overall_prec, 4),
            "Recall": round(overall_rec, 4),
            "F1": round(overall_f1, 4)
        }

        df = pd.DataFrame(rows)
        df_summary = pd.concat([df, pd.DataFrame([summary_row])], ignore_index=True)

        text_report = []
        text_report.append("===============================================================================")
        text_report.append("                      PII REDACTION EVALUATION REPORT                          ")
        text_report.append("===============================================================================\n")
        text_report.append(f"{'Entity':<18} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10}")
        text_report.append("-" * 79)

        for _, row in df_summary.iterrows():
            if row['Entity'] == 'OVERALL':
                text_report.append("-" * 79)
            text_report.append(
                f"{row['Entity']:<18} | {row['TP']:<4} | {row['FP']:<4} | {row['FN']:<4} | "
                f"{row['Precision']:<10.2%} | {row['Recall']:<10.2%} | {row['F1']:<10.2%}"
            )

        text_report.append("===============================================================================")
        text_report.append(f"Overall Precision: {overall_prec:.2%}")
        text_report.append(f"Overall Recall:    {overall_rec:.2%}")
        text_report.append(f"Overall F1-Score:  {overall_f1:.2%}")
        text_report.append("===============================================================================")

        report_str = "\n".join(text_report)
        return df_summary, report_str

    def save_reports(self, df: pd.DataFrame, report_str: str, csv_path: str = "evaluation_report.csv", txt_path: str = "metrics.txt") -> None:
        """Saves evaluation results to CSV and text report files."""
        os.makedirs(os.path.dirname(csv_path) if os.path.dirname(csv_path) else ".", exist_ok=True)
        os.makedirs(os.path.dirname(txt_path) if os.path.dirname(txt_path) else ".", exist_ok=True)

        df.to_csv(csv_path, index=False)
        logger.info(f"Saved evaluation report CSV to: {csv_path}")

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(report_str)
        logger.info(f"Saved metrics text summary to: {txt_path}")
