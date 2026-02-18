from datetime import datetime
import database as db
import pdfprint as pdf


# ============================================================
# CATEGORIES
# Defined once here so both functions.py and app.py can use it.
# In app.py: import functions, then pass functions.CATEGORIES to templates.
# ============================================================
CATEGORIES = {
    1: "food",
    2: "house",
    3: "transport",
    4: "clothes",
    5: "savings",
    6: "misc"
}


# ============================================================
# BUDGET LIMIT CHECK
# Called after adding a transaction to warn if over/near budget.
# Returns a string message instead of printing.
# ============================================================
def check_budget_limit(category, t_type, amount, month, year):
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT amount FROM budgets WHERE category=? AND t_type=? AND year=? AND month=?",
        (category, t_type, year, month)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return f"No budget set for {category} ({t_type}) in {month}/{year}."

    budget_amount = float(row[0])

    cursor.execute(
        "SELECT SUM(amount) FROM transactions WHERE category=? AND t_type=? AND strftime('%Y', date)=? AND strftime('%m', date)=?",
        (category, t_type, str(year), f"{month:02}")
    )
    total_spent = cursor.fetchone()[0] or 0.0
    total_spent += amount
    conn.close()

    msg = f"Budget: £{budget_amount:.2f} | Spent: £{total_spent:.2f} | Remaining: £{budget_amount - total_spent:.2f}"

    if total_spent > budget_amount:
        return "⚠️ ALERT: You have exceeded your budget! " + msg
    elif total_spent > 0.8 * budget_amount:
        return "⚠️ Warning: Nearing budget limit. " + msg

    return "✓ Transaction added. " + msg


# ============================================================
# ADD TRANSACTION (SQL only)
# Low-level insert — called by add_transaction() below.
# ============================================================
def add_transaction_sql(amount, t_type, category, date, description):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transactions (amount, t_type, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (amount, t_type, category, date, description)
    )
    conn.commit()
    conn.close()


# ============================================================
# ADD TRANSACTION (called from Flask route)
# Accepts all values as parameters—no input() calls.
# Returns a string result message for the flash() in app.py.
# ============================================================
def add_transaction(amount, t_type, category, year, month, day, desc):
    try:
        date = datetime(int(year), int(month), int(day))
    except ValueError:
        return "Invalid date provided. Transaction not added."

    add_transaction_sql(float(amount), t_type, category, date, desc)
    budget_msg = check_budget_limit(category, t_type, float(amount), int(month), int(year))
    return f"Transaction added successfully. {budget_msg}"


# ============================================================
# ADD BUDGET (SQL only)
# ============================================================
def add_budget_sql(category, t_type, amount, month, year, description):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO budgets(category, t_type, amount, month, year, description) VALUES (?, ?, ?, ?, ?, ?)",
        (category, t_type, amount, month, year, description)
    )
    conn.commit()
    conn.close()


# ============================================================
# CREATE BUDGET (called from Flask route)
# ============================================================
def create_budget(category, t_type, amount, month, year, desc):
    add_budget_sql(category, t_type, float(amount), int(month), int(year), desc)
    t_label = "Income" if t_type == "I" else "Expense"
    return f"Budget set successfully: {category} | {t_label} | £{float(amount):.2f} | {month}/{year}"


# ============================================================
# DISPLAY TRANSACTIONS
# Returns a list of dicts — one per transaction row.
# The template loops over this list to build the table.
# ============================================================
def display_transaction():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions ORDER BY date ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    result = []
    for row in rows:
        id_, amount, t_type, category, date, desc = row
        result.append({
            "id":       id_,
            "amount":   f"£{float(amount):.2f}",
            "type":     "Income" if t_type == "I" else "Expense",
            "category": category,
            "date":     date,
            "desc":     desc or ""
        })
    return result


# ============================================================
# DISPLAY BUDGETS
# Returns a list of dicts — one per budget row.
# ============================================================
def display_budget():
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE budgets SET amount = 0 WHERE amount = ''")
    conn.commit()

    cursor.execute("SELECT * FROM budgets ORDER BY month ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    result = []
    for row in rows:
        id_, category, t_type, amount, month, year, desc = row
        result.append({
            "id":       id_,
            "category": category,
            "type":     "Income" if t_type == "I" else "Expense",
            "amount":   f"£{float(amount):.2f}",
            "month":    month,
            "year":     year,
            "desc":     desc or ""
        })
    return result


# ============================================================
# SHOW SUMMARY
# Returns a list of dicts with budget vs spending data.
# The 'alert' key is 'danger', 'warning', or None.
# ============================================================
def show_summary():
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            b.category,
            b.t_type,
            b.amount AS budget_amount,
            b.month,
            b.year,
            IFNULL(SUM(t.amount), 0) AS total_spent
        FROM budgets b
        LEFT JOIN transactions t
            ON b.category = t.category
            AND b.t_type = t.t_type
            AND strftime('%Y', t.date) = CAST(b.year AS TEXT)
            AND strftime('%m', t.date) = printf('%02d', b.month)
        GROUP BY b.category, b.t_type, b.year, b.month
        ORDER BY b.year, b.month, b.category
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    result = []
    for row in rows:
        category, t_type, budget_amount, month, year, total_spent = row
        budget_amount = float(budget_amount)
        total_spent   = float(total_spent)
        remaining     = budget_amount - total_spent

        alert = None
        if total_spent > budget_amount:
            alert = "danger"
        elif total_spent > 0.8 * budget_amount:
            alert = "warning"

        result.append({
            "category": category,
            "type":     "Income" if t_type == "I" else "Expense",
            "budget":   f"£{budget_amount:.2f}",
            "spent":    f"£{total_spent:.2f}",
            "remaining":f"£{remaining:.2f}",
            "month":    month,
            "year":     year,
            "alert":    alert
        })
    return result


# ============================================================
# CLEAR TABLES
# Deletes all data and resets auto-increment IDs.
# ============================================================
def clear_tables():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM budgets")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='transactions'")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='budgets'")
    conn.commit()
    conn.close()
    return "All transactions and budgets cleared successfully. IDs reset to 1."


# ============================================================
# PRINT TRANSACTION HISTORY AS PDF
# ============================================================
def print_transaction_history():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions ORDER BY date ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "No transactions to print."

    content = ["<b>Transaction History</b><br><br>"]
    for row in rows:
        id_, amount, t_type, category, date, desc = row
        t_type_full = "Income" if t_type == "I" else "Expense"
        content.append(f"[{id_}] £{float(amount):.2f} | {t_type_full} | {category} | {date} | {desc}")

    pdf.generate_pdf("transaction_history.pdf", content)
    return "transaction_history.pdf generated successfully."


# ============================================================
# PRINT MONTHLY BUDGET AS PDF
# ============================================================
def print_monthly_budget():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM budgets ORDER BY month ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "No budgets to print."

    content = ["<b>Budget History</b><br><br>"]
    for row in rows:
        id_, category, t_type, amount, month, year, desc = row
        t_type_full = "Income" if t_type == "I" else "Expense"
        content.append(f"[{id_}] {category} | {t_type_full} | £{float(amount):.2f} | {month}/{year} | {desc}")

    pdf.generate_pdf("budget_history.pdf", content)
    return "budget_history.pdf generated successfully."