import subprocess
import sys
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_step(name: str, cmd: list) -> bool:
    logging.info(f"STARTING STEP: {name}")
    logging.info(f"Command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd="/opt/crovia/CROVIA_DEV")
        logging.info(f"STEP COMPLETED: {name}")
        logging.info(f"Output:\n{result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"STEP FAILED: {name}")
        logging.error(f"Exit code: {e.returncode}")
        logging.error(f"Stdout:\n{e.stdout}")
        logging.error(f"Stderr:\n{e.stderr}")
        return False
    except Exception as e:
        logging.error(f"UNEXPECTED ERROR in {name}: {str(e)}")
        return False

def main():
    logging.info("=== CROVIA V3 PIPELINE DAEMON STARTED ===")
    
    python_exec = "python3"
    
    steps = [
        ("Import Ledger", [python_exec, "scripts/import_ledger.py"]),
        ("Build Lineage Graph V3", [python_exec, "scripts/build_lineage_graph.py"]),
        ("Lineage Discrepancies", [python_exec, "scripts/lineage_discrepancies.py"]),
        ("Import TPA Ledger", [python_exec, "scripts/import_tpa_ledger.py"]),
        ("Import Outreach Ledger", [python_exec, "scripts/import_outreach_ledger.py"]),
        ("Export Outreach V4", [python_exec, "scripts/export_outreach_v4.py"]),
        ("Enrich Outreach V4", [python_exec, "scripts/enrich_outreach_v4.py"]),
        ("Build Lineage Graph V4", [python_exec, "scripts/build_lineage_graph_v4.py"]),
        ("Rebuild Compliance Index", [python_exec, "scripts/rebuild_compliance_index.py"]),
        ("Export Webroot V3", [python_exec, "scripts/export_webroot_v3.py"])
    ]
    
    for name, cmd in steps:
        success = run_step(name, cmd)
        if not success:
            logging.error(f"PIPELINE ABORTED AT STEP: {name}")
            sys.exit(1)
            
    logging.info("=== CROVIA V3 PIPELINE COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    main()
