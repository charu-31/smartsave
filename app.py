from flask import Flask,render_template, request, redirect
from flask import session
import pandas as pd
import sqlite3
import plotly.express as px
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from flask import send_file
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


app = Flask(__name__)
app.secret_key = "your-secret-key"


@app.route("/")
def home():
   
    return render_template("register.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT SUM(amount)
    FROM expenses
    WHERE user_id = ?
    AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    """, (session["user_id"],))
    total_expenses = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM expenses
    WHERE user_id = ?
    AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    """, (session["user_id"],))
    total_transactions = cursor.fetchone()[0]

    cursor.execute("""
    SELECT SUM(amount)
    FROM income
    WHERE user_id = ?
    """, (session["user_id"],))
    total_income = cursor.fetchone()[0]

    cursor.execute("""
    SELECT category, SUM(amount)
    FROM expenses
    WHERE user_id = ?
    AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    GROUP BY category
    """, (session["user_id"],))
    category_data = cursor.fetchall()

    cursor.execute("""
    SELECT category, SUM(amount)
    FROM expenses
    WHERE user_id = ?
    AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    GROUP BY category
    ORDER BY SUM(amount) DESC
    LIMIT 1
    """, (session["user_id"],))

    top_category = cursor.fetchone()

    cursor.execute("""
    SELECT SUM(amount)
    FROM expenses
    WHERE user_id = ?
    AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    """, (session["user_id"],))

    this_month = cursor.fetchone()[0]

    cursor.execute("""
    SELECT SUM(amount)
    FROM expenses
    WHERE user_id=?
    AND strftime('%Y-%m', date) =
    strftime('%Y-%m', 'now', '-1 month')
    """,(session["user_id"],))

    last_month = cursor.fetchone()[0]

    cursor.execute("""
    SELECT
    strftime('%Y-%m', date) as month,
    SUM(amount)
    FROM expenses
    WHERE user_id=?
    GROUP BY month
    ORDER BY month
    """)

    monthly_data = cursor.fetchall()

    cursor.execute("""
    SELECT strftime('%Y-%m', date), SUM(amount)
    FROM income
    WHERE user_id = ?
    GROUP BY strftime('%Y-%m', date)
    ORDER BY date
    """, (session["user_id"],))

    income_history = cursor.fetchall()

    cursor.execute("""
    SELECT strftime('%Y-%m', date), SUM(amount)
    FROM expenses
    WHERE user_id = ?
    GROUP BY strftime('%Y-%m', date)
    ORDER BY date
    """, (session["user_id"],))

    expense_history = cursor.fetchall()

    months = []
    monthly_totals = []

    for row in monthly_data:
        if row[1] is not None:
            months.append(row[0])
            monthly_totals.append(float(row[1]))

    if months and monthly_totals:
        line_fig = px.line(
            x=months,
            y=monthly_totals,
            markers=True,
            title="Monthly Expense Trend"
        )

        line_graph = line_fig.to_html(full_html=False)

    else:
        line_graph = None

    categories = []
    amounts = []

    for category in category_data:
        categories.append(category[0])
        amounts.append(category[1])

    if categories and amounts:
        fig = px.pie(
            names=categories,
            values=amounts,
            title="Expense Distribution"
        )

        graph_html = fig.to_html(full_html=False)

    else:
        graph_html = None

    cursor.execute("""
SELECT bill_name, due_date
FROM reminders
WHERE user_id = ?
ORDER BY due_date ASC
LIMIT 3
""", (session["user_id"],))

    reminders = cursor.fetchall()
    conn.close()

    if total_expenses is None:
        total_expenses = 0

    

    if total_income is None:
        total_income = 0

    savings = total_income - total_expenses
    if total_income > 0:
        savings_rate = round((savings / total_income) * 100, 2)
    else:
        savings_rate = 0
    if savings_rate >= 40:
        health_score = "Excellent 🟢"

    elif savings_rate >= 20:
        health_score = "Good 🟡"

    else:
        health_score = "Needs Improvement 🔴"

    if top_category:
        highest_category = top_category[0]
    else:
        highest_category = "None"
    
    if this_month is None:
        this_month = 0

    if last_month is None:
        last_month = 0
    if last_month > 0:
        change_percent = round(
            ((this_month - last_month) / last_month) * 100,2
    )
    else:
     change_percent = 0

    streak = 0

    for i in range(
        min(len(income_history), len(expense_history))):

        if income_history[i][1] > expense_history[i][1]:
            streak += 1
        else:
            streak = 0

    return render_template(
        "dashboard.html",
        total_expenses=total_expenses,
        total_transactions=total_transactions,
        total_income=total_income,
        savings=savings,
        savings_rate=savings_rate,
        health_score=health_score,
        highest_category=highest_category,
        this_month=this_month,
        last_month=last_month,
        change_percent=change_percent,
        username=session['username'],
        streak=streak,
        reminders=reminders,
        category_data=category_data,
        graph_html=graph_html,
        line_graph=line_graph
    )

@app.route("/add_expense", methods=["GET", "POST"])
def add_expense():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        amount = request.form["amount"]
        category = request.form["category"]
        description = request.form["description"]

        conn = sqlite3.connect("finance.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO expenses(user_id, amount, description,category, date)
        VALUES (?,?, ?, ?, date('now'))
        """, (session["user_id"],amount, description,category))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("add_expense.html")

@app.route("/expense")
def expense():

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM expenses
    WHERE user_id = ?
    ORDER BY id DESC
    """, (session["user_id"],))

    expenses = cursor.fetchall()

    conn.close()

    return render_template(
        "expense.html",
        expenses=expenses
    )
@app.route("/add_income", methods=["GET","POST"])
def add_income():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        amount = request.form["amount"]
        source = request.form["source"]

        conn = sqlite3.connect("finance.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO income(user_id,amount, source, date)
        VALUES (?,?, ?, date('now'))
        """, (session["user_id"],amount, source))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("add_income.html")

@app.route("/budget")
def budget():

    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()

    cursor.execute("""
SELECT category, budget_amount
FROM budgets
WHERE user_id = ?
""", (session["user_id"],))
    budgets = cursor.fetchall()

    budget_data = []

    for category, budget in budgets:

        cursor.execute("""
SELECT SUM(amount)
FROM expenses
WHERE user_id = ?
AND LOWER(TRIM(category)) = LOWER(TRIM(?))
""", (session["user_id"], category))
        spent = cursor.fetchone()[0] or 0

        used_percent = round((spent / budget) * 100, 1) if budget > 0 else 0

        budget_data.append({
            "category": category,
            "budget": budget,
            "spent": spent,
            "used_percent": used_percent
        })

    conn.close()

    return render_template(
        "budget.html",
        budget_data=budget_data
    )
    

@app.route("/add_budget", methods=["GET", "POST"])
def add_budget():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        category = request.form["category"]
        amount = float(request.form["amount"])

        conn = sqlite3.connect("finance.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT OR REPLACE INTO budgets
        (user_id,category, budget_amount)
        VALUES (?,?, ?)
        """, (session["user_id"],category, amount))

        conn.commit()
        conn.close()

        return redirect("/budget")

    return render_template("add_budget.html")
@app.route("/insights")
def insights():

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()

    insights = []

    # Budget query
    cursor.execute("""
    SELECT category, budget_amount
    FROM budgets
    WHERE user_id = ?
    """, (session["user_id"],))
    
    budgets = cursor.fetchall()
    cursor.execute("""
SELECT SUM(amount)
FROM income
WHERE user_id = ?
AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
""", (session["user_id"],))

    total_income = cursor.fetchone()[0] or 0

    cursor.execute("""
    SELECT SUM(amount)
    FROM expenses
    WHERE user_id = ?
    AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    """, (session["user_id"],))

    total_expenses = cursor.fetchone()[0] or 0

    savings = total_income - total_expenses

    if total_income > 0:
        savings_rate = (savings / total_income) * 100
    else:
        savings_rate = 0

    # Risk warning logic here 👇
    from datetime import datetime
    import calendar

    today = datetime.now()

    days_passed = today.day

    total_days = calendar.monthrange(
        today.year,
        today.month
    )[1]

    month_progress = (
        days_passed / total_days
    ) * 100

    if savings_rate < 20:
        insights.append(
        "🧠 Your spending style: High spender this month.")

    elif savings_rate < 40:
        insights.append(
        "🧠 Your spending style: Balanced spender.")

    else:
        insights.append(
        "🧠 Your spending style: Strong saver.")

    for category, budget in budgets:

        cursor.execute("""
        SELECT SUM(amount)
        FROM expenses
        WHERE user_id = ?
        AND category = ?
        AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
        """, (
    session["user_id"],category
    ))

        spent = cursor.fetchone()[0] or 0

        usage_percent = (
            spent / budget
        ) * 100

        if usage_percent > month_progress + 20:

            insights.append(
                f"⚠️ {category} budget may be exceeded before month end."
            )
        # =========================
# ANOMALY DETECTOR
# =========================

    cursor.execute("""
        SELECT category
        FROM expenses
        WHERE user_id = ?
        AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
        GROUP BY category
        """, (session["user_id"],))

    categories = cursor.fetchall()

    for category in categories:

        category_name = category[0]

    # Average monthly spending
    cursor.execute("""
    SELECT AVG(month_total)
    FROM (
        SELECT SUM(amount) AS month_total
        FROM expenses
        WHERE user_id=? AND category=?
        GROUP BY strftime('%Y-%m', date)
    )
    """, (session["user_id"],category_name,))

    avg_spending = cursor.fetchone()[0] or 0

    # Current month spending
    cursor.execute("""
    SELECT SUM(amount)
    FROM expenses
    WHERE user_id=? AND category=?
    AND strftime('%Y-%m', date)
        = strftime('%Y-%m', 'now')
    """, (session["user_id"],category_name,))

    current_spending = cursor.fetchone()[0] or 0

    if avg_spending > 0:

        change_percent = (
            (current_spending - avg_spending)
            / avg_spending
        ) * 100

        if change_percent > 50:

            insights.append(
                f"🚨 {category_name} spending is "
                f"{change_percent:.0f}% higher than your average. "
                f"Review recent purchases."
            )

        elif change_percent < -30:

            insights.append(
                f"✅ Great job! {category_name} spending is "
                f"{abs(change_percent):.0f}% lower than your average."
                )
    cursor.execute("""
    SELECT category, SUM(amount)
    FROM expenses
    WHERE user_id = ?
    AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    GROUP BY category
    ORDER BY SUM(amount) DESC
    LIMIT 1
    """, (session["user_id"],))

    top_category = cursor.fetchone()

    if top_category and total_expenses > 0:

        category_name = top_category[0]
        category_amount = top_category[1]

    percent = (
        category_amount / total_expenses
    ) * 100

    insights.append(
        f"📌 {category_name} took {percent:.0f}% of your spending this month."
    )

    conn.close()   # ✅ CLOSE HERE

    return render_template(
        "insights.html",
        insights=insights
    )
@app.route("/budget_splitter", methods=["GET","POST"])
def budget_splitter():

    if "user_id" not in session:
        return redirect("/login")

    suggestions = []

    if request.method == "POST":

        income = float(request.form["income"])

        savings_percent = float(
            request.form["savings_percent"]
        )

        available_budget = (
            income * (100-savings_percent)
        ) / 100
        conn = sqlite3.connect("finance.db")
        cursor = conn.cursor()

        cursor.execute("""
        SELECT category,
               SUM(amount)
        FROM expenses
        WHERE user_id=?
        GROUP BY category
        """,(session["user_id"],))

        data = cursor.fetchall()
        conn.close()
        total_spent = sum(row[1] for row in data)
        for category, amount in data:

            percentage = (amount / total_spent) * 100

            suggested_budget = (available_budget* percentage) / 100

            suggestions.append({
                "category": category,
                "percent": round(percentage,2),
                "budget": round(suggested_budget,2)
            })
    return render_template(
        "budget_splitter.html",
        suggestions=suggestions)

@app.route("/goal_planner", methods=["GET", "POST"])
def goal_planner():

    if "user_id" not in session:
        return redirect("/login")
    result=None
    if request.method == "POST":

        goal_name = request.form["goal_name"]
        goal_amount = float(request.form["goal_amount"])

        conn = sqlite3.connect("finance.db")
        cursor = conn.cursor()

        cursor.execute("""
        SELECT SUM(amount)
        FROM income
        WHERE user_id = ?
        """, (session["user_id"],))

        income = cursor.fetchone()[0] or 0

        cursor.execute("""
        SELECT SUM(amount)
        FROM expenses
        WHERE user_id = ?
        """, (session["user_id"],))
        

        expenses = cursor.fetchone()[0] or 0

        cursor.execute("""
        INSERT INTO goals (user_id, goal_name, target_amount)
        VALUES (?, ?, ?)
        """, (
        session["user_id"],
        goal_name,
        goal_amount
        ))

        conn.commit()
        conn.close()

        monthly_savings = income - expenses

        if monthly_savings > 0:

            months_needed = round(
                goal_amount / monthly_savings,
                1
            )

            required_for_12 = round(
                goal_amount / 12,
                2
            )

            result = {
                "goal_name": goal_name,
                "goal_amount": goal_amount,
                "monthly_savings": monthly_savings,
                "months_needed": months_needed,
                "required_for_12": required_for_12
            }

        else:

            result = {
                "error":
                "Current savings are zero or negative."
            }

    return render_template(
        "goal_planner.html",
        result=result
    )
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == "POST":

        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("finance.db")
        cursor = conn.cursor()

        # Check if email already exists
        cursor.execute("""
        SELECT * FROM users
        WHERE email = ?
        """, (email,))

        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return "Email already exists"

        # Insert new user
        cursor.execute("""
        INSERT INTO users
        (username, email, password)
        VALUES (?, ?, ?)
        """, (username, email, hashed_password))

        conn.commit()
        conn.close()

        return redirect('login')

    return render_template("register.html")

    
@app.route('/login', methods=['GET','POST'])
def login():

    if request.method == "POST":

        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect("finance.db")
        cursor = conn.cursor()

        cursor.execute("""
        SELECT * FROM users
        WHERE email = ?
        """,(email,))

        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user[3], password):

            session['user_id'] = user[0]
            session['username'] = user[1]

            return redirect('/dashboard')

        return "Invalid Email or Password"

    return render_template("login.html")

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login')

@app.route("/report", methods=["GET", "POST"])
def report():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        name = session["username"]
        report_month = request.form["report_month"]

        # Connect database
        conn = sqlite3.connect("finance.db")
        cursor = conn.cursor()

        # Total Income
        cursor.execute("""
        SELECT SUM(amount)
        FROM income
        WHERE user_id = ?
        AND strftime('%Y-%m', date) = ?
        """, (session["user_id"], report_month))
        total_income = cursor.fetchone()[0] or 0

        # Total Expenses
        cursor.execute("""
        SELECT SUM(amount)
FROM expenses
WHERE user_id = ?
AND strftime('%Y-%m', date) = ?
""", (session["user_id"], report_month))
        total_expenses = cursor.fetchone()[0] or 0

        # Total Savings
        total_savings = total_income - total_expenses

        # Fetch budgets
        cursor.execute("""
        SELECT category, budget_amount
        FROM budgets
        WHERE user_id = ?
        """, (session["user_id"],))
        budgets = cursor.fetchall()

        # Fetch latest goal
        cursor.execute("""
        SELECT goal_name, target_amount
        FROM goals
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """, (session["user_id"],))
        goal = cursor.fetchone()

        print("Fetched Goal:", goal)

        if goal:
            goal_name = goal[0]
            goal_amount = goal[1]
        else:
            goal_name = "No Goal"
            goal_amount = 0

        conn.close()

        # Goal calculations
        if goal_amount > 0:
            completion = (total_savings / goal_amount) * 100

            if total_savings > 0:
                months_left = goal_amount / total_savings
            else:
                months_left = 0
        else:
            completion = 0
            months_left = 0

        # Create PDF
        file_name = "finance_report.pdf"

        pdf = SimpleDocTemplate(file_name)
        styles = getSampleStyleSheet()

        elements = []

        # =========================
        # PAGE 1
        # =========================

        elements.append(
            Paragraph(
                "AI Finance Tracker Report",
                styles["Title"]
            )
        )

        elements.append(Spacer(1, 20))

        elements.append(
            Paragraph(
                f"Account Holder: {name}",
                styles["Normal"]
            )
        )

        elements.append(Spacer(1, 20))

        # AI Summary
        if total_savings > 0:
            summary = (
                f"Great work {name}! "
                f"Your current savings are Rs.{total_savings:.2f}."
            )
        else:
            summary = (
                f"Warning {name}: "
                f"Your expenses exceeded your income."
            )

        elements.append(
            Paragraph(
                summary,
                styles["BodyText"]
            )
        )

        elements.append(Spacer(1, 20))

        # Financial Snapshot Table
        snapshot = [
            ["Total Income", f"Rs.{total_income:.2f}"],
            ["Total Expenses", f"Rs.{total_expenses:.2f}"],
            ["Total Savings", f"Rs.{total_savings:.2f}"]
        ]

        snapshot_table = Table(snapshot)

        snapshot_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.lightblue),
                ("GRID", (0, 0), (-1, -1), 1, colors.black)
            ])
        )

        elements.append(snapshot_table)

        # PAGE BREAK SPACE
        elements.append(Spacer(1, 50))

        # =========================
        # PAGE 2
        # =========================

        elements.append(
            Paragraph(
                "Budget Summary",
                styles["Heading2"]
            )
        )

        elements.append(Spacer(1, 20))

        budget_data = [["Category", "Budget"]]

        for category, amount in budgets:
            budget_data.append(
                [category, f"Rs.{amount:.2f}"]
            )

        budget_table = Table(budget_data)

        budget_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 1, colors.black)
            ])
        )

        elements.append(budget_table)

        elements.append(Spacer(1, 50))

        # =========================
        # PAGE 3
        # =========================

        elements.append(
            Paragraph(
                "Goal Planner & Forecast",
                styles["Heading2"]
            )
        )

        elements.append(Spacer(1, 20))

        goal_data = [
            ["Goal Name", goal_name],
            ["Target Amount", f"Rs.{goal_amount:.2f}"],
            ["Saved", f"Rs.{total_savings:.2f}"],
            ["Completion", f"{completion:.2f}%"],
            ["Months Left", f"{months_left:.1f}"]
        ]

        goal_table = Table(goal_data)

        goal_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.lightgreen),
                ("GRID", (0, 0), (-1, -1), 1, colors.black)
            ])
        )

        elements.append(goal_table)

        elements.append(Spacer(1, 20))

        forecast = (
            f"If you continue saving at this rate, "
            f"you may achieve your goal '{goal_name}' "
            f"in {months_left:.1f} months."
        )

        elements.append(
            Paragraph(
                forecast,
                styles["BodyText"]
            )
        )

        # Build PDF
        pdf.build(elements)

        return send_file(
            file_name,
            as_attachment=True
        )

    return render_template("report.html")
@app.route("/add_reminder", methods=["GET", "POST"])
def add_reminder():

    if request.method == "POST":

        bill_name = request.form["bill_name"]
        due_date = request.form["due_date"]

        conn = sqlite3.connect("finance.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO reminders
        (user_id, bill_name, due_date)
        VALUES (?, ?, ?)
        """, (
            session["user_id"],
            bill_name,
            due_date
        ))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("add_reminder.html")

@app.route("/search_expenses", methods=["GET", "POST"])
def search_expenses():

    results = []

    if request.method == "POST":

        category = request.form["category"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        min_amount = request.form["min_amount"]

        conn = sqlite3.connect("finance.db")
        cursor = conn.cursor()

        query = query = """
SELECT amount, category, description, date
FROM expenses
WHERE user_id = ?
"""
        values = [session["user_id"]]

        if category:
            query += " AND category LIKE ?"
            values.append(f"%{category}%")

        if start_date and end_date:
            query += " AND date BETWEEN ? AND ?"
            values.extend([start_date, end_date])

        if min_amount:
            query += " AND amount >= ?"
            values.append(min_amount)

        cursor.execute(query, values)

        results = cursor.fetchall()
        conn.close()

    return render_template(
        "search_expenses.html",
        results=results
    )
@app.route("/delete_expense/<int:expense_id>")
def delete_expense(expense_id):

    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM expenses
    WHERE id = ?
    AND user_id = ?
    """, (expense_id, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect("/")




        

if __name__ == "__main__":
    app.run(debug=True)