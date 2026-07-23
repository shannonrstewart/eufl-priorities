from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from analyze_eu_forced_labor_exposure import main

if __name__ == "__main__":
    main()
