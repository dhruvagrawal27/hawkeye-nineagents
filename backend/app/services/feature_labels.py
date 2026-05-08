"""Plain-English labels and value formatters for the 146 model features.

Used by SHAP factor display and the Settings → Feature Registry table.
For features without an explicit entry, we fall back to the bare feature name.
"""

from __future__ import annotations

# Curated mapping for the features that drive 95% of SHAP mass for mules.
# Generated from RBI NFPC Phase 2 feature dictionary; non-listed features
# default to {"label": <name>, "format": "raw"}.

LABELS: dict[str, dict[str, str]] = {
    # Pass-through / structuring (highest-mass mule signals)
    "pass_rate":  {"label": "Balance pass-through rate",         "format": "pct",   "normal": "<5%"},
    "thru":       {"label": "Throughput ratio",                  "format": "ratio", "normal": "~1×"},
    "ps45":       {"label": "Structuring 40-45K share",          "format": "pct",   "normal": "<2%"},
    "ps49":       {"label": "Structuring 45-49K share",          "format": "pct",   "normal": "<2%"},
    "fan_ratio":  {"label": "Counterparty fan-in ratio",         "format": "ratio", "normal": "~1×"},
    "trp":        {"label": "Transactions per recipient",        "format": "raw"},
    # Off-hours / weekend
    "pngt":       {"label": "Off-hours transaction share",       "format": "pct",   "normal": "<10%"},
    "pwkd":       {"label": "Weekend transaction share",         "format": "pct"},
    "pbiz":       {"label": "Business-hours transaction share",  "format": "pct"},
    "hrs":        {"label": "Active hours coverage",             "format": "raw"},
    # Volume / velocity
    "n":          {"label": "Total transactions",                "format": "int"},
    "ndays":      {"label": "Active days",                       "format": "int"},
    "tpd":        {"label": "Transactions per active day",       "format": "raw"},
    "ncp":        {"label": "Distinct counterparties",           "format": "int"},
    "txn_per_month": {"label": "Average transactions / month",   "format": "raw"},
    "amt_per_month": {"label": "Average INR / month",            "format": "inr"},
    "mean_amt":   {"label": "Mean transaction amount",           "format": "inr"},
    "std_amt":    {"label": "Std-dev of transaction amount",     "format": "inr"},
    "cv_amt":     {"label": "CV of transaction amount",          "format": "ratio"},
    "mx":         {"label": "Largest transaction amount",        "format": "inr"},
    "amt_range":  {"label": "Amount spread (max-min)",           "format": "inr"},
    "sa":         {"label": "Sum of debits",                     "format": "inr"},
    "sc":         {"label": "Count of credits",                  "format": "int"},
    "sd":         {"label": "Count of debits",                   "format": "int"},
    "cr":         {"label": "Credit-debit ratio",                "format": "ratio"},
    # Bursts (b_ family)
    "b_max_vol":     {"label": "Peak monthly INR volume",        "format": "inr"},
    "b_burst_months":{"label": "Months in burst state",          "format": "int"},
    "b_n_months":    {"label": "Active months",                  "format": "int"},
    "b_max_cps":     {"label": "Peak counterparties / month",    "format": "int"},
    "b_max_r50k":    {"label": "Peak fraction txns ≥ 50K",       "format": "pct"},
    "b_max_xlg":     {"label": "Peak fraction extra-large txns", "format": "pct"},
    "b_active_frac": {"label": "Active month fraction",          "format": "pct"},
    "b_gini":        {"label": "Monthly volume Gini",            "format": "ratio"},
    "b_cv":          {"label": "Monthly volume CV",              "format": "ratio"},
    # Graph (g_ family)
    "g_ncp":         {"label": "Graph counterparty count",       "format": "int"},
    "g_tew":         {"label": "Graph total edge weight",        "format": "inr"},
    "g_cvew":        {"label": "Graph edge-weight CV",            "format": "ratio"},
    "g_nec":         {"label": "Graph total edge count",         "format": "int"},
    "g_avg_txn_per_cp": {"label": "Avg transactions per counterparty", "format": "raw"},
    "g_nexcl":       {"label": "Excluded counterparty count",    "format": "int"},
    "g_wmsn":        {"label": "Weighted mule-shared (norm.)",   "format": "ratio"},
    "g_gt5":         {"label": "Counterparties with >5 txns",    "format": "int"},
    "g_gt10":        {"label": "Counterparties with >10 txns",   "format": "int"},
    "g_gt30":        {"label": "Counterparties with >30 txns",   "format": "int"},
    "g_gt50":        {"label": "Counterparties with >50 txns",   "format": "int"},
    "g_mcs_per_cp":  {"label": "Mule-CP score per counterparty", "format": "ratio"},
    "span":          {"label": "Activity time span (days)",      "format": "int"},
    "nch":           {"label": "Distinct channels used",         "format": "int"},
    "nmcc":          {"label": "Distinct MCC codes",             "format": "int"},
    "n_months":      {"label": "Months with activity",           "format": "int"},
    "nfr":           {"label": "Foreign-channel txn count",      "format": "int"},
    "pt":            {"label": "Peak-time txn share",            "format": "pct"},
    "dcov":          {"label": "Day coverage",                   "format": "ratio"},
    "cppt":          {"label": "Counterparties per 100 txns",    "format": "raw"},
    "cdr":           {"label": "Credit-debit difference ratio",  "format": "ratio"},
    "fan_asymm":     {"label": "Counterparty fan asymmetry",     "format": "ratio"},
    "p_mbd":         {"label": "Multi-bank-day share",           "format": "pct"},
    "b_burst_frac":  {"label": "Burst-month fraction",           "format": "pct"},
    "b_spike_ratio": {"label": "Burst spike ratio",              "format": "ratio"},
    "b_peak_recency":{"label": "Days since peak month",          "format": "int"},
    "b_cp_spike":    {"label": "Counterparty-spike score",       "format": "ratio"},
    "b_mom_max_jump":{"label": "Largest month-over-month jump",  "format": "ratio"},
    "bal_mean":      {"label": "Mean balance",                   "format": "inr"},
    "bal_std":       {"label": "Std-dev of balance",             "format": "inr"},
    "bal_min":       {"label": "Minimum balance",                "format": "inr"},
    "bal_max":       {"label": "Maximum balance",                "format": "inr"},
    "bal_range":     {"label": "Balance range",                  "format": "inr"},
    "bal_cv":        {"label": "Balance CV",                     "format": "ratio"},
    "branch_employee_count":{"label": "Branch employee count",   "format": "int"},
    "branch_turnover":{"label": "Branch turnover (yearly)",      "format": "ratio"},
    "branch_asset_size":{"label": "Branch asset size",           "format": "inr"},
    "bt":            {"label": "Branch tier",                    "format": "raw"},
    "tpb":           {"label": "Transactions per branch employee","format":"raw"},
    "atb":           {"label": "Avg transactions per branch",    "format": "raw"},
    "rel_y":         {"label": "Relationship years",             "format": "raw"},
    "bmd":           {"label": "Months since first txn",         "format": "int"},
    "bqd":           {"label": "Quarters since first txn",       "format": "int"},
    "loan_sum":      {"label": "Total open loan amount",         "format": "inr"},
    "cc_sum":        {"label": "Total credit-card amount",       "format": "inr"},
    "ka_sum":        {"label": "Total kisan-account amount",     "format": "inr"},
    "ka_count":      {"label": "Kisan account count",            "format": "int"},
    "sa_sum":        {"label": "Savings sum",                    "format": "inr"},
    "sa_count":      {"label": "Savings count",                  "format": "int"},
    "monthly_avg_balance":{"label": "Monthly avg balance",       "format": "inr"},
    "quarterly_avg_balance":{"label": "Quarterly avg balance",   "format": "inr"},
    "avg_balance":   {"label": "Average balance",                "format": "inr"},
    "num_chequebooks":{"label": "Number of chequebooks",         "format": "int"},
    "product_code":  {"label": "Account product code",           "format": "raw"},
    "age":           {"label": "Customer age",                   "format": "int"},
    "pmed":          {"label": "Medium-amount txn share",        "format": "pct"},
    "psml":          {"label": "Small-amount txn share",         "format": "pct"},
    "pmic":          {"label": "Micro-amount txn share",         "format": "pct"},
    "g_top1":        {"label": "Top-1 counterparty share",       "format": "pct"},
    "g_top3":        {"label": "Top-3 counterparty share",       "format": "pct"},
    "g_hhi":         {"label": "Graph HHI concentration",        "format": "ratio"},
    "g_mcs":         {"label": "Mule-counterparty score",        "format": "ratio"},
    "g_mcm":         {"label": "Mule-counterparty mean",         "format": "ratio"},
    "g_mcx":         {"label": "Mule-counterparty max",          "format": "ratio"},
    "g_wms":         {"label": "Weighted mule-shared",           "format": "ratio"},
    "g_pexcl":       {"label": "Excluded counterparty share",    "format": "pct"},
    "g_mule_users_max": {"label": "Max known mule users on shared CPs", "format": "int"},
    "g_mule_users_sum": {"label": "Sum of known mule users on shared CPs", "format": "int"},
    # IP / device
    "n_unique_ips":  {"label": "Unique IPs in window",           "format": "int"},
    "ip_mule_shared":{"label": "IPs shared with known mules",    "format": "int"},
    "ip_has_mule_ip":{"label": "Has used a known mule IP",       "format": "bool"},
    "ip_mule_rate":  {"label": "Fraction txns from mule IPs",    "format": "pct"},
    # Account meta
    "kyc_e":         {"label": "KYC completeness score",         "format": "ratio"},
    "kyc_d":         {"label": "Days since KYC",                 "format": "int"},
    "age_d":         {"label": "Account age (days)",             "format": "int"},
    "rur":           {"label": "Rural-branch flag",              "format": "bool"},
    "nri":           {"label": "NRI flag",                       "format": "bool"},
    "pmjdy":         {"label": "Jan Dhan account flag",          "format": "bool"},
    "regular":       {"label": "Regular account flag",           "format": "bool"},
    "male":          {"label": "Male flag",                      "format": "bool"},
    "jnt":           {"label": "Joint account flag",             "format": "bool"},
    "has_mob_change":{"label": "Mobile changed in window",       "format": "bool"},
    "mob_change_days":{"label": "Days since last mobile change", "format": "int"},
    "mob_change_recent":{"label": "Mobile changed recently",     "format": "bool"},
    "new_acct_high_vol":{"label": "New account with high volume","format": "bool"},
    "nacct":         {"label": "Number of related accounts",     "format": "int"},
    "loan_count":    {"label": "Open loan count",                "format": "int"},
    "od_count":      {"label": "Open OD count",                  "format": "int"},
    "od_sum":        {"label": "Open OD sum",                    "format": "inr"},
    "cc_count":      {"label": "Credit card count",              "format": "int"},
    # Balance
    "daily_avg_balance":{"label": "Daily average balance",       "format": "inr"},
    "bal_n":         {"label": "Distinct balance snapshots",     "format": "int"},
    # Channels
    "atm":  {"label": "ATM channel share",   "format": "pct"},
    "mob":  {"label": "Mobile channel share","format": "pct"},
    "int":  {"label": "Internet channel share","format":"pct"},
    "cre":  {"label": "Cross-channel ratio", "format": "ratio"},
    "dem":  {"label": "Demat channel share", "format": "pct"},
    "fas":  {"label": "FASTag channel share","format": "pct"},
    "ndig": {"label": "Digital onboarding flag", "format": "bool"},
    "pan":  {"label": "PAN provided flag",   "format": "bool"},
    "pf":   {"label": "Profile completeness","format": "ratio"},
    "nom":  {"label": "Nominee assigned flag","format": "bool"},
    "chk_a":{"label": "Cheque-active flag",  "format": "bool"},
    "chk_v":{"label": "Cheque velocity",     "format": "raw"},
    # Range buckets
    "pr1k":  {"label": "Txn share ≤1K",   "format": "pct"},
    "pr5k":  {"label": "Txn share 1K-5K", "format": "pct"},
    "pr10k": {"label": "Txn share 5K-10K","format": "pct"},
    "pr25k": {"label": "Txn share 10K-25K","format":"pct"},
    "pr50k": {"label": "Txn share 25K-50K","format":"pct"},
    "pxlg":  {"label": "Extra-large txn share","format":"pct"},
    "plrg":  {"label": "Large txn share", "format": "pct"},
}


def label_for(feature: str) -> str:
    return LABELS.get(feature, {}).get("label") or feature


def format_value(feature: str, value: float) -> str:
    fmt = LABELS.get(feature, {}).get("format", "raw")
    try:
        if fmt == "pct":
            return f"{float(value) * 100:.1f}%"
        if fmt == "ratio":
            return f"{float(value):.2f}×"
        if fmt == "int":
            return f"{int(round(float(value))):,}"
        if fmt == "inr":
            v = float(value)
            if abs(v) >= 1e7:
                return f"₹{v / 1e7:.2f} Cr"
            if abs(v) >= 1e5:
                return f"₹{v / 1e5:.2f} L"
            return f"₹{v:,.0f}"
        if fmt == "bool":
            return "Yes" if float(value) >= 0.5 else "No"
    except (TypeError, ValueError):
        pass
    return f"{float(value):.4f}"


def normal_band(feature: str) -> str | None:
    return LABELS.get(feature, {}).get("normal")
