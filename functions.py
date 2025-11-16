from datetime import datetime

import database as db
import pdfprint as pdf


def t_type_choice():
    """Prompts the user to choose between incomes and expenses"""
    while True:
        t_type = input("Type (I for Income, E for Expense): ").strip().upper()
        if t_type in ("I", "E"):
            return t_type
        print("Incorrect input. Please choose 'I' for Income or 'E' for Expense.")


def check_budget_limit(category, t_type, amount, month, year):
    """Warn the user if spending is near or exceeds the budget"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT amount FROM budgets WHERE category=? AND t_type=? AND year=? AND month=?",
        (category, t_type, year, month)
    )
    row = cursor.fetchone()

    if not row:
        print(f"No budget set for {category} ({t_type}) in {month}/{year}.")
        conn.close()
        return

    budget_amount = float(row[0])

    cursor.execute(
        "SELECT SUM(amount) FROM transactions WHERE category=? AND t_type=? AND strftime('%Y', date)=? AND strftime('%m', date)=?",
        (category, t_type, str(year), f"{month:02}")
    )
    total_spent = cursor.fetchone()[0] or 0.0
    total_spent += amount  # include the new transaction

    if total_spent > budget_amount:
        print("\n*** ALERT: You have exceeded your budget! ***")
    elif total_spent > 0.8 * budget_amount:
        print("\n*** Warning: You are nearing your budget limit! ***")

    print(f"Budget: £{budget_amount:.2f}, Spent: £{total_spent:.2f}, Remaining: £{budget_amount - total_spent:.2f}\n")

    conn.close()

def choose_category():
    categories = {
        1: "food",
        2: "house",
        3: "transport",
        4: "clothes",
        5: "savings",
        6: "misc"
    }
    print("\nAvailable categories:")
    for key, value in categories.items():
        print(f"{key}. {value}")

    while True:
        try:
            choice = int(input("Choose a category number: "))
            selected_category = categories.get(choice)
            if selected_category:
                return selected_category
            else:
                print("Invalid choice. Try again.")
        except ValueError:
            print("Please enter a valid number.")


def add_transaction_sql(amount, t_type, category, date, description):
    # Create a database to store the added data
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transactions (amount, t_type, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (amount, t_type, category, date, description)
    )
    conn.commit()
    conn.close()


def add_budget_sql(category, t_type, amount, month, year, description):
    """Budget creator in the spreadsheet"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO budgets(category, t_type, amount, month, year, description) VALUES (?, ?, ?, ?, ?, ?)",
        (category, t_type, amount, month, year, description)
    )
    conn.commit()
    conn.close()


def show_summary():
    """Show the summary of the budget against the transaction history"""
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
        print("\nNo summary available! Add budgets or transactions first.")
        return

    print("\n========== SUMMARY ==========")

    for row in rows:
        category, t_type, budget_amount, month, year, total_spent = row
        remaining = budget_amount - total_spent

        t_type_full = "Income" if t_type == "I" else "Expense"

        print(f"\n📌 {category.upper()} ({t_type_full}) — {month}/{year}")
        print(f"   Budget:    £{budget_amount:.2f}")
        print(f"   Spent:     £{total_spent:.2f}")
        print(f"   Remaining: £{remaining:.2f}")

        # Alerts
        if total_spent > budget_amount:
            print("   ⚠️ ALERT: Budget EXCEEDED!")
        elif total_spent > 0.8 * budget_amount:
            print("   ⚠️ Warning: Nearing budget limit.")

    print("\n==============================\n")


def add_transaction():
    amount = float(input("Enter transaction amount : "))
    t_type = t_type_choice()

    category = choose_category()
    try:
        year = int(input("Year (YYYY): "))
        month = int(input("Month (1-12): "))
        day = int(input("Day (1-31): "))
        date = datetime(year, month, day)
    except ValueError:
        print("Invalid date provided. Transaction not added.")
        return
    desc = input("Give a short description of the transaction: ")

    transaction = {
        " amount": amount,
        "t_type": t_type,
        "category": category,
        "date": date,
        "description": desc,
    }
    add_transaction_sql(amount, t_type, category, date, desc)
    check_budget_limit(category, t_type, amount, month, year)
    print(transaction)


def create_budget():
    category = choose_category()
    if not category:
        print("Category cannot be empty")
        return

    t_type = t_type_choice()
    amount = float(input("Amount in £ : ").strip())
    desc = input("Short description : ")
    month = int(input("Month (choose from 1-12) : "))
    year = int(input("Year(YYYY) : "))

    add_budget_sql(category, t_type, amount, month, year, desc)
    print(f"Budget set: {category}, {month}/{year}, {'Income' if t_type == 'I' else 'Expense'}")
    print(f"  Amount: £{amount:.2f}")
    print(f"  Description: {desc}")


def display_transaction():
    """Display  all the transactions"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM TRANSACTIONS ORDER BY date ASC"
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\nNo values found!!!")
        return

    print("\n=== Transaction History ===")
    for row in rows:
        id_, amount, t_type, category, date, desc = row
        t_type_full = "Income" if t_type == "I" else "Expense"
        print(f"[{id_}] £{amount:.2f} | {t_type_full} | {category} | {date} | {desc}")


def clear_tables():
    conn = db.get_connection()
    cursor = conn.cursor()

    # Delete all rows from transactions and budgets
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM budgets")

    # Reset auto-increment IDs
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='transactions'")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='budgets'")

    conn.commit()
    conn.close()
    print("All transactions and budgets have been cleared, IDs reset to 1.")

def display_budget():
    """Display the monthly budget"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE budgets SET amount = 0 WHERE amount = ''")
    conn.commit()  # commit the update

    # 2️⃣ Then, fetch the budgets
    cursor.execute("SELECT * FROM budgets ORDER BY month ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\nNo values found!!!")
        return

    print("\n=== Budget History ===")
    for row in rows:
        id_, category, t_type, amount, month, year, desc = row  # matches table
        amount = float(amount)
        t_type_full = "Income" if t_type == "I" else "Expense"
        print(f"[{id_}] {category} | {t_type_full} | £{amount:.2f} | {month}/{year} | {desc}")



def print_transaction_history():
    """Print it as PDF"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM transactions ORDER BY date ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No transactions to print!")
        return

    content = ["<b>Transaction History</b><br><br>"]

    for row in rows:
        id_, amount, t_type, category, date, desc = row
        t_type_full = "Income" if t_type == "I" else "Expense"
        content.append(
            f"[{id_}] £{amount:.2f} | {t_type_full} | {category} | {date} | {desc}"
        )

    pdf.generate_pdf("transaction_history.pdf", content)



def print_monthly_budget():
    """Print it as a PDF"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM budgets ORDER BY date ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("Not budgets to Print!")
        return
    content = ["<b>Budget History</b><br><br>"]

    for row in rows:
        id_, category, t_type, amount, month, year, desc = row
        t_type_full = "Income" if t_type == "I" else "Expense"
        content.append(
            f"[{id_}] {category} | {t_type_full} | £{amount:.2f} | {month}/{year} | {desc}"
        )

    pdf.generate_pdf("budget_history.pdf", content)


def show_main_menu():
    """Main menu"""

    menu = """
    1. Create Budget
    2. Add Transaction
    3. Display Transaction
    4. Display Budget
    5. Print Monthly Budget
    6. Print Transaction History
    7. Clear Tables
    8. Show Summary
    """
    print(menu)


def get_user_choice(user_input):
    actions={
        1:create_budget,
        2:add_transaction,
        3:display_transaction,
        4:display_budget,
        5:print_monthly_budget,
        6:print_transaction_history,
        7:clear_tables,
        8:show_summary
    }

    if user_input == 0:
        print("Now exiting")
        return False

    action = actions.get(user_input)

    if action:
        action()  # call the stored function
    else:
        print("Invalid option.")

    return True

