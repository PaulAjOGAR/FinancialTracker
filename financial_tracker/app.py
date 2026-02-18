from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import functions_web as functions
import database as db

app = Flask(__name__)
app.secret_key = "change-this-to-something-random-in-production"

db.create_tables()


@app.route("/")
def index():
    transactions = functions.display_transaction()

    total_income   = sum(float(t['amount'].replace('£','')) for t in transactions if t['type'] == 'Income')
    total_expenses = sum(float(t['amount'].replace('£','')) for t in transactions if t['type'] == 'Expense')
    net = total_income - total_expenses

    return render_template(
        "index.html",
        total_income=total_income,
        total_expenses=total_expenses,
        net=net
    )


@app.route("/add-transaction", methods=["GET", "POST"])
def add_transaction():
    if request.method == "POST":
        msg = functions.add_transaction(          # NOT add_transaction_sql
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


if __name__ == "__main__":
    app.run(debug=True)