import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

from datetime import datetime

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute(
        "SELECT symbol, SUM(shares) AS total_shares FROM purchases WHERE user_id = ? GROUP BY symbol",
        session["user_id"],
    )
    portfolio = []
    total_stock_value = 0
    # Appending information for stocks of each stock symbol
    for row in rows:
        stock = lookup(row["symbol"])
        if row["total_shares"] != 0:
            stock_value = row["total_shares"] * stock["price"]
            total_stock_value += stock_value
            portfolio.append(
                {
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "shares": row["total_shares"],
                    "price": usd(stock["price"]),
                    "total": usd(stock_value),
                }
            )

    # Fetch user's cash balance
    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash_balance = user_cash[0]["cash"]
    # Render index.html and pass variables as parameters
    portfolio_total = cash_balance + total_stock_value
    return render_template(
        "index.html",
        portfolio=portfolio,
        cash=usd(cash_balance),
        total=usd(portfolio_total),
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # Get symbol
        symbol = request.form.get("symbol")
        # Get shares
        shares = request.form.get("shares")

        stock = lookup(symbol)
        # Validating input
        if not stock:
            return apology("stock symbol does not exist", 400)

        try:
            shares_int = int(shares)
        except (ValueError, TypeError):
            return apology("number of shares must be a whole number", 400)

        if shares_int < 1:
            return apology("number of shares must be positive", 400)

        price = stock["price"]
        cost = price * shares_int
        user_id = session["user_id"]

        # Getting User's Cash
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        if not cash or cost > cash[0]["cash"]:
            return apology("insufficient funds for this purchase", 400)

        # Time of purchase
        timestamp = datetime.now()

        # Record the purchase
        db.execute(
            "INSERT INTO purchases (user_id, symbol, shares, price) VALUES (:user_id, :symbol, :shares, :price)",
            user_id=user_id,
            symbol=stock["symbol"],
            shares=shares_int,
            price=price,
        )

        # Update user's cash after the purchase
        remaining_cash = cash[0]["cash"] - cost
        db.execute(
            "UPDATE users SET cash = :remaining_cash WHERE id = :user_id",
            remaining_cash=remaining_cash,
            user_id=user_id,
        )

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute(
        "SELECT symbol, shares, price, timestamp FROM purchases WHERE user_id = ?",
        session["user_id"],
    )
    transactions = []
    # Generating history of transactions row by row
    for row in rows:
        stock = lookup(row["symbol"])
        if stock:
            transactions.append(
                {
                    "symbol": stock["symbol"],
                    "shares": row["shares"],
                    "price": usd(row["price"]),
                    "transacted": row["timestamp"],
                }
            )

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("stock symbol does not exist", 400)
        # Rendering quoted.html with passed values
        return render_template(
            "quoted.html",
            name=stock["name"],
            symbol=stock["symbol"],
            price=usd(stock["price"]),
        )
    else:
        return render_template("quote.html")


@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    """Add cash to account"""
    if request.method == "POST":
        cash_ammount = request.form.get("amount")
        # Validating input
        try:
            cash_ammount = int(cash_ammount)
        except (ValueError, TypeError):
            return apology("cash amount must be a number", 400)

        if cash_ammount < 0:
            return apology("cash amount must be a positive value")
        # Updating cash amount
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        curr_cash = cash[0]["cash"]
        updated_cash = curr_cash + cash_ammount
        db.execute(
            "UPDATE users SET cash = :updated_cash WHERE id = :user_id",
            updated_cash=updated_cash,
            user_id=session["user_id"],
        )
        return redirect("/")
    else:
        return render_template("addcash.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        # Ensure password was confirmed
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)
        elif not (request.form.get("password") == request.form.get("confirmation")):
            return apology("passwords must match", 400)
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        if user:
            return apology("username already taken", 400)

        # Adding a user

        db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            request.form.get("username"),
            generate_password_hash(request.form.get("password")),
        )

        rows = db.execute(
            "SELECT id FROM users WHERE username = ?", request.form.get("username")
        )
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        # Validating input
        if not symbol:
            return apology("must select a stock to sell", 400)

        stocks = lookup(symbol)
        if not stocks:
            return apology("stock symbol does not exist", 400)

        user_id = session["user_id"]
        # Getting sum of shares for selected stock symbol
        curr_shares = db.execute(
            "SELECT SUM(shares) AS total_shares FROM purchases WHERE user_id = :user_id AND symbol = :symbol GROUP BY symbol",
            user_id=user_id,
            symbol=stocks["symbol"],
        )

        if not curr_shares:
            return apology("you don't own any shares of this stock")

        curr_shares = curr_shares[0]["total_shares"]

        shares = request.form.get("shares")
        # Validating input
        try:
            shares_int = int(shares)
        except (ValueError, TypeError):
            return apology("number of shares must be a whole number", 400)

        if shares_int < 1:
            return apology("number of shares must be positive")

        if shares_int > curr_shares:
            return apology("you don't own this many shares of this stock", 400)

        stocks = lookup(symbol)
        price = stocks["price"]
        # Updating cash amount based on sold stocks
        revenue = price * shares_int
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        remaining_cash = cash[0]["cash"] + revenue
        db.execute(
            "UPDATE users SET cash = :remaining_cash WHERE id = :user_id",
            remaining_cash=remaining_cash,
            user_id=user_id,
        )
        # Adding transaction into purchases database
        db.execute(
            "INSERT INTO purchases (user_id, symbol, shares, price) VALUES (:user_id, :symbol, :shares, :price)",
            user_id=user_id,
            symbol=stocks["symbol"],
            shares=shares_int * -1,
            price=price,
        )

        return redirect("/")

    else:
        user_id = session["user_id"]
        # Retrieve the stocks that the user owns
        stocks = db.execute(
            "SELECT symbol , SUM(shares) AS total_shares FROM purchases WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0",
            user_id,
        )
        # Render sell.html with stocks variable passed to it
        return render_template("sell.html", stocks=stocks)
