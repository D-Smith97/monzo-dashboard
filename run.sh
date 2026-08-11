#!/bin/bash
set -e

# Default parameters (can be overridden via command line args)
CSV_FILE="${1:-statement.csv}"
MAIN_BAL="${2:--540.00}"
FLEX_BAL="${3:-2560.00}"

echo "=========================================="
echo "    Monzo Command Centre Automation       "
echo "=========================================="

# Ensure virtual environment exists
if [ ! -d "venv" ]; then
    echo "[*] Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if not already present
if [ ! -f "venv/.installed" ]; then
    echo "[*] Installing required packages (pandas, python-dotenv)..."
    pip install --upgrade pip > /dev/null
    pip install pandas python-dotenv > /dev/null
    touch venv/.installed
fi

echo "[*] Parsing statement: $CSV_FILE"
echo "[*] Using balances -> Main: £$MAIN_BAL | Flex: £$FLEX_BAL"

# Run Python script
python process.py "$CSV_FILE" --main "$MAIN_BAL" --flex "$FLEX_BAL"

echo "=========================================="
echo " Finished! Refresh your local web view.   "
echo "=========================================="
