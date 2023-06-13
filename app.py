import os

import sqlite3
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

#need for history
from datetime import datetime

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# connecting to database
db_connection = sqlite3.connect("finance.db", check_same_thread=False)

# create cursor object to interact with database
db = db_connection.cursor()

# Make sure API key is set
# if not os.environ.get("API_KEY"):
#     raise RuntimeError("API_KEY not set")


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
    id = session["user_id"]
    symbols = db.execute("SELECT symbol FROM portfolios WHERE PersonID=?", (id,)).fetchall()
    cash = db.execute("SELECT cash FROM users WHERE id=?", (id,)).fetchone()

    for symbol in symbols:
        results = lookup(symbol["symbol"])
        if results:
            price = results['price']
            portfolio = db.execute("UPDATE portfolios SET price=? WHERE PersonID=? AND symbol=?", (price, id, symbol["symbol"]))
            db_connection.commit()
        else:
            return apology("error loading symbols", 400)

    # Hiding values for shares=0 but should probably instead remove these rows from table
    portfolio = db.execute("SELECT symbol, companyName, price, shares, price*shares AS holding_value FROM portfolios WHERE PersonID=? AND shares!=0", (id,)).fetchall()
    total_value = db.execute("SELECT SUM(price*shares) AS total_value FROM portfolios WHERE PersonID=?", (id,)).fetchone()
    if total_value[0] is not None:
        total_value = cash[0] + total_value[0]
    else:
        total_value = cash[0]
    return render_template("index.html", portfolio=portfolio, cash=cash[0], total_value=total_value)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    TransactionType = "buy"
    if request.method == "GET":
        return render_template("buy.html")
    else:
        results = lookup(request.form.get("symbol"))
        # Need to validate they input an int rather than converting here
        if request.form.get("shares").isdigit():
            shares = int(request.form.get("shares"))
        else:
            return apology("Please enter a whole integer of shares to buy", 400)

        if results:
            name = results['name']
            symbol = results['symbol']
            price = results['price']
            id = session["user_id"]
            cash = db.execute("SELECT cash FROM users WHERE id=?", id).fetchone()
            total_price = float(shares) * price
            value = usd(total_price)

            if shares <= 0:
                return apology("Enter at least 1 share to buy", 400)
            elif total_price > cash[0]:
                return apology("Not enough cash", 400)
            else:
                now = datetime.now()
                db.execute("UPDATE portfolios SET shares=shares+? WHERE PersonID=? AND symbol=?", (shares, id, symbol))
                db.execute("INSERT INTO portfolios (PersonID, companyName, symbol, price, shares) SELECT ?, ?, ?, ?, ? WHERE NOT EXISTS (SELECT symbol FROM portfolios WHERE PersonID=? AND symbol=?)", (id, name, symbol, price, shares, id, symbol))
                db.execute("INSERT INTO transactions (PersonID, TransactionType, companyName, symbol, price, shares, OrderDate) SELECT ?, ?, ?, ?, ?, ?, ?", (id, TransactionType, name, symbol, price, shares, now))
                db.execute("UPDATE users SET cash=cash-? WHERE id=?", (total_price, id))
                db_connection.commit()

                cash = db.execute("SELECT cash FROM users WHERE id=?", (id,)).fetchone()
                total_value = db.execute("SELECT SUM(price*shares) AS total_value FROM portfolios WHERE PersonID=?", (id,)).fetchone()
                total_value = usd(cash[0] + total_value[0])

                cash_left = usd(cash[0])
                price=usd(price)

                return render_template("buy.html", success="Purchase Successful!", total=value, available=cash_left, symbol=symbol, name=name, price=price, shares=shares, total_available=total_value)

        else:
            return apology("Enter valid symbol and share number", 400)



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    id = session["user_id"]
    transactions = db.execute("SELECT TransactionType, symbol, price, shares, OrderDate FROM transactions WHERE PersonID=? ORDER BY OrderDate DESC", (id,)).fetchall()
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
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", (request.form.get("username"),))
        user = rows.fetchone()

        # Ensure username exists and password is correct
        if user is None or not check_password_hash(user[2], request.form.get("password")):
            return apology("invalid username and/or password", 400)
        
        # Remember which user has logged in
        session["user_id"] = user[0]

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
    if request.method == "GET":
        return render_template("quote.html")

    else:
        results = lookup(request.form.get("symbol"))
        if results:
            name = results['name']
            symbol = results['symbol']
            price = results['price']
            value = usd(price)
            return render_template("quote.html", quote="1 Share is", value=value)
        else:
            return apology("symbol not found", 400)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        check = db.execute("SELECT username FROM users WHERE username=?", (username,))

        if not username:
            return apology("must provide a username", 400)

        elif not password:
            return apology("must provide a password", 400)

        # personal touch; require password of length 6 to 16 characters long
        elif len(password) < 6 or len(password) > 16:
            return apology("password must be 6 to 16 charactes long", 400)

        elif password != confirmation:
            return apology("passwords do not match", 400)

        elif check.fetchone() is not None:
            return apology("username already exists", 400)

        else:
            hash = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", (username, hash))
            db_connection.commit()
            return render_template("success.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    id = session["user_id"]
    symbols = db.execute("SELECT symbol FROM portfolios WHERE PersonID=?", (id,)).fetchall()
    TransactionType = "sell"
    if request.method == "GET":
        return render_template("sell.html", symbols=symbols)
    else:
        results = lookup(request.form.get("symbol"))
        # Need to validate they input an int rather than converting here
        shares = int(request.form.get("shares"))
        if results:
            name = results['name']
            symbol = results['symbol']
            price = results['price']
            shares_owned = db.execute("SELECT shares FROM portfolios WHERE PersonID=? AND symbol=?", (id, symbol)).fetchone()
            total_price = float(shares) * price
            if shares <= 0:
                return apology("Enter at least 1 share to sell", 400)
            elif shares > shares_owned[0]:
                return apology("You do not own that many shares", 400)
            else:
                for x in symbols:
                    if x[0] == symbol:
                        now = datetime.now()
                        db.execute("UPDATE portfolios SET shares=shares-? WHERE PersonID=? AND symbol=?", (shares, id, symbol))
                        db.execute("INSERT INTO transactions (PersonID, TransactionType, companyName, symbol, price, shares, OrderDate) SELECT ?, ?, ?, ?, ?, ?, ?", (id, TransactionType, name, symbol, price, shares, now))
                        db.execute("UPDATE users SET cash=cash+? WHERE id=?", (total_price, id))
                        db_connection.commit()

                        cash = db.execute("SELECT cash FROM users WHERE id=?", id).fetchone()
                        total_value = db.execute("SELECT SUM(price*shares) AS total_value FROM portfolios WHERE PersonID=?", (id,)).fetchone()
                        total_value = usd(cash[0] + total_value[0])

                        cash_left = usd(cash[0])
                        total_price = usd(total_price)
                        price = usd(price)
                        return render_template("sell.html", success="Sale Successful!", name=name, symbol=symbol, price=price, shares=shares, total=total_price, available=cash_left, total_available=total_value)
            return apology("You do not own shares of that symbol", 400)


        else:
            return apology("symbol does not exist", 400)


#route for successful registration
@app.route("/success", methods=["POST"])
def success():
    return render_template("login.html")