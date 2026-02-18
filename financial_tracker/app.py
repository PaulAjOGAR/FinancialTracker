from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from collections import defaultdict
from datetime import datetime
import functions_web as functions
import database as db
import file_import
import json

app = Flask(__name__)
app.secret_key = "change-this-to-something-random-in-production"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db.create_tables()


@app.route("/")
def index():
    transactions = functions.display_transaction()

    total_income   = sum(float(t['amount'].replace('£','')) for t in transactions if t['type'] == 'Income')
    total_expenses = sum(float(t['amount'].replace('£','')) for t in transactions if t['type'] == 'Expense')
    net = total_income - total_expenses
    transaction_count = len(transactions)

    cat_totals = defaultdict(float)
    for t in transactions:
        if t['type'] == 'Expense':
            cat_totals[t['category'].capitalize()] += float(t['amount'].replace('£',''))
    category_data = {'labels': list(cat_totals.keys()), 'data': list(cat_totals.values())} if cat_totals else None

    monthly_income   = defaultdict(float)
    monthly_expenses = defaultdict(float)
    for t in transactions:
        try:
            parts = str(t['date']).split('-')
            label = f"{parts[1]}/{parts[0][2:]}"
        except Exception:
            label = str(t['date'])[:7]
        if t['type'] == 'Income':
            monthly_income[label]   += float(t['amount'].replace('£',''))
        else:
            monthly_expenses[label] += float(t['amount'].replace('£',''))

    all_months = sorted(set(list(monthly_income.keys()) + list(monthly_expenses.keys())))
    monthly_data = {
        'labels':   all_months,
        'income':   [monthly_income.get(m, 0)   for m in all_months],
        'expenses': [monthly_expenses.get(m, 0) for m in all_months]
    } if all_months else None

    expense_by_date = defaultdict(float)
    for t in transactions:
        if t['type'] == 'Expense':
            expense_by_date[str(t['date'])[:10]] += float(t['amount'].replace('£',''))

    timeline_data = None
    if expense_by_date:
        sorted_dates = sorted(expense_by_date.keys())
        running, cumulative = 0, []
        for d in sorted_dates:
            running += expense_by_date[d]
            cumulative.append(round(running, 2))
        timeline_data = {'labels': sorted_dates, 'data': cumulative}

    return render_template(
        "index.html",
        total_income=total_income,
        total_expenses=total_expenses,
        net=net,
        transaction_count=transaction_count,
        category_data=category_data,
        monthly_data=monthly_data,
        timeline_data=timeline_data
    )


@app.route("/add-transaction", methods=["GET", "POST"])
def add_transaction():
    if request.method == "POST":
        msg = functions.add_transaction(
            request.form["amount"],
            request.form["t_type"],
            request.form["category"],
            request.form["year"],
            request.form["month"],
            request.form["day"],
            request.form.get("desc", "")
        )
        flash(msg, "success" if "successfully" in msg else "error")
        return redirect(url_for("add_transaction"))

    return render_template(
        "form.html",
        form_title="Add Transaction",
        form_subtitle="Record a new income or expense entry.",
        form_action=url_for("add_transaction"),
        categories=functions.CATEGORIES,
        show_date=True,
        show_period=False,
        submit_label="Add Transaction"
    )


@app.route("/create-budget", methods=["GET", "POST"])
def create_budget():
    if request.method == "POST":
        msg = functions.create_budget(
            request.form["category"],
            request.form["t_type"],
            request.form["amount"],
            request.form["month"],
            request.form["year"],
            request.form.get("desc", "")
        )
        flash(msg, "success")
        return redirect(url_for("create_budget"))

    return render_template(
        "form.html",
        form_title="Create Budget",
        form_subtitle="Set a monthly spending target for a category.",
        form_action=url_for("create_budget"),
        categories=functions.CATEGORIES,
        show_date=False,
        show_period=True,
        submit_label="Save Budget"
    )


@app.route("/transactions")
def transactions():
    rows = functions.display_transaction()
    return render_template(
        "table.html",
        page_title="Transactions",
        page_subtitle="Your full transaction history.",
        rows=rows,
        columns=["ID", "Amount", "Type", "Category", "Date", "Description"],
        add_url=url_for("add_transaction"),
        print_url=url_for("print_transactions")
    )


@app.route("/budgets")
def budgets():
    rows = functions.display_budget()
    return render_template(
        "table.html",
        page_title="Budgets",
        page_subtitle="Your monthly budget targets.",
        rows=rows,
        columns=["ID", "Category", "Type", "Amount", "Period", "Description"],
        add_url=url_for("create_budget"),
        print_url=url_for("print_budget")
    )


@app.route("/summary")
def summary():
    rows = functions.show_summary()
    return render_template("summary.html", rows=rows)


@app.route("/clear", methods=["GET", "POST"])
def clear():
    if request.method == "POST":
        msg = functions.clear_tables()
        flash(msg, "success")
        return redirect(url_for("index"))
    return render_template("confirm_clear.html")


@app.route("/print-transactions")
def print_transactions():
    msg = functions.print_transaction_history()
    if "successfully" in msg:
        return send_file("transaction_history.pdf", as_attachment=True)
    flash(msg, "error")
    return redirect(url_for("transactions"))


@app.route("/print-budget")
def print_budget():
    msg = functions.print_monthly_budget()
    if "successfully" in msg:
        return send_file("budget_history.pdf", as_attachment=True)
    flash(msg, "error")
    return redirect(url_for("budgets"))


@app.route("/import", methods=["GET", "POST"])
def import_transactions():
    if request.method == "POST":
        if 'file' not in request.files:
            flash("No file selected.", "error")
            return redirect(url_for("import_transactions"))
        f = request.files['file']
        if not f.filename:
            flash("No file selected.", "error")
            return redirect(url_for("import_transactions"))
        try:
            file_bytes = f.read()
            result = file_import.parse_file(f.filename, file_bytes)
            # Write parsed transactions to a temp file to avoid session size limits
            import tempfile, os
            tmp = os.path.join(tempfile.gettempdir(), 'ft_pending_import.json')
            open(tmp,'w').write(json.dumps(result['transactions']))
            return render_template("import.html", preview=result, filename=f.filename)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("import_transactions"))
        except Exception as e:
            flash(f"Could not parse file: {str(e)}", "error")
            return redirect(url_for("import_transactions"))
    return render_template("import.html", preview=None, filename=None)


@app.route("/import/confirm", methods=["POST"])
def import_confirm():
    import tempfile, os
    tmp = os.path.join(tempfile.gettempdir(), 'ft_pending_import.json')
    if not os.path.exists(tmp):
        flash('Import session expired. Please upload the file again.', 'error')
        return redirect(url_for('import_transactions'))
    transactions = json.loads(open(tmp).read())
    os.remove(tmp)

    imported = 0
    skipped  = 0
    conn = db.get_connection()
    cursor = conn.cursor()
    for t in transactions:
        if not t.get('amount') or not t.get('t_type'):
            skipped += 1
            continue
        try:
            date_str = t.get('date', datetime.today().strftime('%Y-%m-%d'))
            cursor.execute(
                "INSERT INTO transactions (amount, t_type, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (float(t['amount']), t['t_type'], t.get('category', 'misc'), date_str, t.get('description', ''))
            )
            imported += 1
        except Exception as e:
            print(f'Import row error: {e}')
            skipped += 1
    conn.commit()
    conn.close()

    flash(
        f"Successfully imported {imported} transaction{'s' if imported != 1 else ''}."
        + (f" {skipped} row{'s' if skipped != 1 else ''} skipped." if skipped else ""),
        "success" if imported > 0 else "error"
    )
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)