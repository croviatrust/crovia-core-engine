#!/usr/bin/env python3
"""
CROVIA Forensics Runner
========================

Runs disclosure forensics analysis and:
1. Generates verified_findings.json for HF dataset
2. Sends email alert to info@croviatrust.com if verified findings exist

Designed to run after export_ddf_to_hf.py in the GitHub Action.
"""

import json
import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from pathlib import Path

# Add PRO engine to path
PRO_ENGINE_PATH = Path(__file__).parent.parent / "crovia-pro-engine"
sys.path.insert(0, str(PRO_ENGINE_PATH))

from croviapro.forensics import BulletproofForensicsEngine, Confidence


def run_forensics(dataset_root: str) -> dict:
    """Run forensics analysis and return report."""
    
    drift_path = os.path.join(dataset_root, "open", "drift", "ddf_drift_events_30d.jsonl")
    snapshots_path = os.path.join(dataset_root, "open", "drift", "ddf_snapshots_latest.jsonl")
    
    engine = BulletproofForensicsEngine(
        drift_events_path=drift_path,
        snapshots_path=snapshots_path
    )
    engine.load()
    engine.run_analysis()
    
    return engine.to_report()


def save_verified_findings(report: dict, output_path: str):
    """Save verified findings to JSON file."""
    
    # Filter only verified/high confidence findings
    verified = [
        f for f in report.get("findings", [])
        if f.get("confidence") in ["VERIFIED", "HIGH"]
    ]
    
    output = {
        "schema": "crovia.pro.verified_findings.v1",
        "generated_at": report.get("generated_at"),
        "engine_version": report.get("engine_version"),
        "total_events_analyzed": report.get("total_events"),
        "clean_events": report.get("clean_events"),
        "verified_findings_count": len(verified),
        "verified_findings": verified
    }
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"[FORENSICS] Saved {len(verified)} verified findings to {output_path}")
    return output


def send_email_alert(findings: dict):
    """Send email alert if verified findings exist."""
    
    verified = findings.get("verified_findings", [])
    if not verified:
        print("[FORENSICS] No verified findings - no email sent")
        return False
    
    # Email configuration from environment
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    
    if not smtp_user or not smtp_pass:
        print("[FORENSICS] SMTP credentials not configured - skipping email")
        return False
    
    to_email = "info@croviatrust.com"
    
    # Build email content
    subject = f"🚨 CROVIA Alert: {len(verified)} Verified Anomalies Detected"
    
    body = f"""
CROVIA Disclosure Forensics Alert
==================================

{len(verified)} verified anomalies have been detected in AI disclosure patterns.

Generated: {findings.get('generated_at')}
Events analyzed: {findings.get('total_events_analyzed')}
Clean events: {findings.get('clean_events')}

VERIFIED FINDINGS:
"""
    
    for f in verified:
        body += f"""
---
Date: {f.get('date')}
Confidence: {f.get('confidence')} ({f.get('confidence_score'):.0f}%)
Organizations affected: {f.get('orgs_count')}
Events: {f.get('event_count')}
License removals: {f.get('details', {}).get('license_removals', 0)}
Dataset removals: {f.get('details', {}).get('dataset_removals', 0)}
"""
        if f.get('warnings'):
            body += f"Warnings: {', '.join(f.get('warnings'))}\n"
    
    body += """
---

View full details on the CROVIA Registry Observer:
https://huggingface.co/spaces/Crovia/omission-oracle

This is an automated alert from CROVIA Disclosure Forensics v3.
"""
    
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        print(f"[FORENSICS] Email alert sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"[FORENSICS] Email failed: {e}")
        return False


def main():
    """Main entry point."""
    
    # Determine dataset root
    dataset_root = os.getenv("CROVIA_DATASET_ROOT")
    if not dataset_root:
        # Default: parent of this script's directory
        dataset_root = str(Path(__file__).parent.parent)
    
    print(f"[FORENSICS] Dataset root: {dataset_root}")
    print(f"[FORENSICS] Running analysis...")
    
    # Run forensics
    report = run_forensics(dataset_root)
    
    # Save verified findings
    output_path = os.path.join(dataset_root, "open", "forensic", "verified_findings.json")
    findings = save_verified_findings(report, output_path)
    
    # Send email if findings exist
    send_email_alert(findings)
    
    # Summary
    verified_count = findings.get("verified_findings_count", 0)
    print()
    print("=" * 60)
    print(f"FORENSICS COMPLETE")
    print(f"  Verified findings: {verified_count}")
    print(f"  Output: {output_path}")
    print("=" * 60)
    
    # Exit with code 0 even if no findings (that's normal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
