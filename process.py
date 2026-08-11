import os
import sys
import json
import hashlib
import argparse
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

def d2f(val):
    """Convert Decimal to float safely for JSON serialization with 2 decimal places."""
    return float(val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

def main():
    parser = argparse.ArgumentParser(description="Monzo Financial Engine CLI")
    parser.add_argument("csv_file", type=str, help="Path to the Monzo CSV statement")
    parser.add_argument("--main", type=float, required=True, help="Current main account balance")
    parser.add_argument("--flex", type=float, required=True, help="Current Monzo Flex debt balance")
    args = parser.parse_args()

    od_limit = Decimal(os.getenv("OVERDRAFT_LIMIT", "2000.00"))
    flex_limit = Decimal(os.getenv("FLEX_LIMIT", "3000.00"))
    fixed_bills = json.loads(os.getenv("FIXED_BILLS", "[]"))
    exclude_keywords = [kw.strip().lower() for kw in os.getenv("EXCLUDE_FROM_VARIABLE", "").split(",")]

    if not os.path.exists(args.csv_file):
        print(f"Error: Statement file '{args.csv_file}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        df = pd.read_csv(args.csv_file)
    except Exception as e:
        print(f"Error reading CSV file: {e}", file=sys.stderr)
        sys.exit(1)

    # Sanitize column headers
    df.columns = [c.replace('\ufeff', '').strip().lower() for c in df.columns]

    date_col = next((c for c in df.columns if 'date' in c or 'created' in c or 'transaction date' in c), None)
    amount_col = next((c for c in df.columns if 'amount' in c or 'value' in c), None)
    title_col = next((c for c in df.columns if 'name' in c or 'description' in c or 'title' in c or 'merchant' in c), None)
    cat_col = next((c for c in df.columns if 'category' in c or 'type' in c), None)

    if not date_col or not amount_col:
        print("Error: Could not identify 'Date' or 'Amount' columns in CSV schema.", file=sys.stderr)
        sys.exit(1)

    valid_rows = []
    seen_hashes = set()

    for _, row in df.iterrows():
        raw_date = row[date_col]
        raw_amount = str(row[amount_col])
        clean_amount_str = raw_amount.replace('£', '').replace(',', '').strip()
        
        try:
            parsed_date = pd.to_datetime(raw_date)
            if pd.isna(parsed_date):
                continue
            amount_dec = Decimal(clean_amount_str)
        except Exception:
            continue

        if amount_dec == 0:
            continue

        title_str = str(row[title_col]) if title_col and pd.notna(row[title_col]) else "Unknown"
        
        # Idempotency check via row hashing
        row_hash = hashlib.md5(f"{parsed_date.strftime('%Y-%m-%d')}_{amount_dec}_{title_str}".encode()).hexdigest()
        if row_hash in seen_hashes:
            continue
        seen_hashes.add(row_hash)

        raw_cat = str(row[cat_col]) if cat_col and pd.notna(row[cat_col]) else ""
        
        valid_rows.append({
            'date': parsed_date,
            'amount': amount_dec,
            'title': title_str,
            'category': raw_cat
        })

    if not valid_rows:
        print("Error: No valid transactions parsed from CSV.", file=sys.stderr)
        sys.exit(1)

    valid_rows.sort(key=lambda x: x['date'], reverse=True)
    latest_date = valid_rows[0]['date']
    current_year = latest_date.year
    current_month = latest_date.month
    current_day = latest_date.day
    
    if current_month == 12:
        last_day_of_month = 31
    else:
        last_day_of_month = (datetime(current_year, current_month + 1, 1) - pd.Timedelta(days=1)).day

    days_remaining = max(1, last_day_of_month - current_day)

    month_rows = [r for r in valid_rows if r['date'].year == current_year and r['date'].month == current_month]

    gross_outflow = Decimal('0.00')
    total_inflow = Decimal('0.00')
    fast_food_total = Decimal('0.00')
    variable_outflow = Decimal('0.00')
    category_totals = {}
    merchant_totals = {}

    def infer_category(title, raw_cat):
        if raw_cat and raw_cat.strip() != '' and raw_cat.lower() not in ['uncategorised', 'general']:
            return raw_cat.strip()
        t = title.lower()
        if any(w in t for w in ['asda', 'lidl', 'tesco', 'sainsbury', 'aldi', 'morrisons', 'co-op', 'waitrose']):
            return 'Groceries'
        if any(w in t for w in ['mcdonald', 'kfc', 'uber eats', 'deliveroo', 'burger king', 'subway', 'greggs', 'starbucks', 'costa', 'pizza']):
            return 'Dining & Takeaway'
        if any(w in t for w in ['tfl', 'transport for london', 'uber', 'train', 'national rail', 'bus', 'parking', 'shell', 'bp']):
            return 'Transport'
        if any(w in t for w in ['amazon', 'ebay', 'argos', 'currys']):
            return 'Shopping'
        if any(w in t for w in ['overdraft', 'fee', 'interest', 'charge']):
            return 'Fees & Charges'
        if any(w in t for w in ['gym', 'puregym', 'fitness']):
            return 'Health & Fitness'
        return raw_cat.strip() if raw_cat and raw_cat.strip() != '' else 'General / Uncategorised'

    for r in month_rows:
        amt = r['amount']
        title_lower = r['title'].lower()
        cat = infer_category(title_lower, r['category'])

        if amt > 0:
            total_inflow += amt
        else:
            abs_amt = abs(amt)
            gross_outflow += abs_amt
            if any(w in title_lower for w in ['mcdonald', 'kfc', 'uber eats', 'deliveroo', 'burger king', 'subway']):
                fast_food_total += abs_amt

            is_excluded = any(kw in title_lower for kw in exclude_keywords)
            if not is_excluded:
                variable_outflow += abs_amt
                category_totals[cat] = category_totals.get(cat, Decimal('0.00')) + abs_amt
                merchant_totals[title_lower] = merchant_totals.get(title_lower, Decimal('0.00')) + abs_amt

    daily_rate = (variable_outflow / Decimal(currentDay)) if currentDay > 0 else Decimal('0.00')

    pending_bills = []
    pending_bills_total = Decimal('0.00')
    for bill in fixed_bills:
        exact_day = last_day_of_month if bill['day'] == -1 else bill['day']
        if exact_day > currentDay:
            pending_bills.append({
                "name": bill['name'],
                "amount": bill['amount'],
                "exactDay": exact_day
            })
            pending_bills_total += Decimal(str(bill['amount']))

    main_bal = Decimal(str(args.main))
    flex_bal = Decimal(str(args.flex))

    od_used = min(od_limit, abs(main_bal)) if main_bal < 0 else Decimal('0.00')
    od_headroom = od_limit - od_used
    flex_headroom = flex_limit - flex_bal

    scen_a_total_outflow = pending_bills_total + (daily_rate * Decimal(days_remaining))
    scen_b_total_outflow = pending_bills_total + (Decimal('20.00') * Decimal(days_remaining))

    scen_a_bal = main_bal - scen_a_total_outflow
    scen_b_bal = main_bal - scen_b_total_outflow

    weeks_remaining = max(Decimal('1'), Decimal(str(days_remaining)) / Decimal('7'))
    safe_remaining_pool = max(Decimal('0.00'), main_bal - pending_bills_total)
    weekly_allowance = safe_remaining_pool / weeks_remaining
    target_daily_burn = max(Decimal('5.00'), safe_remaining_pool / Decimal(str(days_remaining)))
    target_buffer_goal = abs(scen_b_bal) + Decimal('150.00')

    if scen_a_bal < 0:
        advisory_status = "Debt Risk Active"
        status_badge_class = "bg-rose-500/10 text-rose-400"
        debt_strategy = f"Your current pace risks deepening your overdraft by £{d2f(abs(scen_a_bal))}. Shift immediately to Scenario B (£20/day cap) to recover ground and prevent penalty interest charges."
        restrictions = f"Fast food & non-essential dining is currently restricted. Your maximum weekly allowance is £{d2f(weeklyAllowance)}. Limit discretionary purchases until fixed rent and utility bills clear."
    else:
        advisory_status = "Optimised"
        status_badge_class = "bg-emerald-500/10 text-emerald-400"
        debt_strategy = f"You are on track to clear the month in positive cash flow. Allocate any end-of-month surplus directly toward reducing Monzo Flex debt (£{d2f(flex_bal)} remaining) to eliminate revolving interest."
        restrictions = "Maintain your daily cap at £20.00 or lower. Ensure grocery shopping is consolidated at budget supermarkets (Asda/Lidl) to protect your weekly cash buffer."

    output_data = {
        "dateString": latest_date.strftime('%B %Y'),
        "daysRemaining": days_remaining,
        "metrics": {
            "grossOutflow": d2f(gross_outflow),
            "totalInflow": d2f(total_inflow),
            "dailyRate": d2f(daily_rate),
            "fastFoodTotal": d2f(fast_food_total)
        },
        "limits": {
            "odUsed": d2f(od_used),
            "odHeadroom": d2f(od_headroom),
            "odPct": d2f((od_used / od_limit) * 100),
            "flexBal": d2f(flex_bal),
            "flexHeadroom": d2f(flex_headroom),
            "flexPct": d2f((flex_bal / flex_limit) * 100)
        },
        "forecast": {
            "pendingBills": pending_bills,
            "pendingBillsTotal": d2f(pending_bills_total),
            "scenA_bal": d2f(scen_a_bal),
            "scenA_odRemaining": d2f(od_limit + scen_a_bal),
            "scenB_bal": d2f(scen_b_bal),
            "scenB_odRemaining": d2f(od_limit + scen_b_bal)
        },
        "advisory": {
            "weeklyAllowance": d2f(weekly_allowance),
            "targetDailyBurn": d2f(target_daily_burn),
            "targetBufferGoal": d2f(target_buffer_goal),
            "debtStrategy": debt_strategy,
            "restrictions": restrictions,
            "advisoryStatus": advisory_status,
            "statusBadgeClass": status_badge_class
        },
        "charts": {
            "categoryTotals": {k: d2f(v) for k, v in category_totals.items()},
            "merchantTotals": {k: d2f(v) for k, v in merchant_totals.items()}
        }
    }

    with open("dashboard_data.json", "w") as f:
        json.dump(output_data, f, indent=2)

    print("Success: Processed statement and generated dashboard_data.json.")

if __name__ == "__main__":
    main()
                                              
