import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    # iterate through portfolio database
    user = session["user_id"]
    # send in information
    portfolio = db.execute("SELECT symbol, SUM(shares) AS shares FROM portfolio WHERE user=:user GROUP BY symbol", user=user)

    total = 0
    for i in portfolio:
        symbol = lookup(i["symbol"])
        i["name"] = symbol["name"]
        shares = i["shares"]
        i["price"] = symbol["price"]
        total += shares * i["price"]
    money = db.execute("SELECT * FROM users WHERE id=:id", id=user)
    money_left = money[0]["cash"]
    total += money_left

    return render_template("index.html", information=portfolio, total=total, money_left=money_left)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        # check for input
        if not request.form.get("symbol"):
            return apology("missing symbol")
        if not request.form.get("shares"):
            return apology("missing shares")
        # check for valid input
        if lookup(request.form.get("symbol")) == None:
            return apology("invalid symbol")
        if float(request.form.get("shares")) < 1:
            return apology("shares cannot be negative")

        # calculate buy price
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        buy = float(lookup(symbol).get("price")) * float(shares)

        # buy if person has enough money
        user = session["user_id"]
        data = db.execute("SELECT cash FROM users WHERE id = :id", id = user)
        money = data[0]["cash"]

        if buy > money:
            return apology("Not Enough Money")

        # insert shares into portfolio

        price = lookup(symbol).get("price")
        db.execute("INSERT INTO portfolio (user, symbol, shares, price, total) VALUES (:user, :symbol, :shares, :price, :total)", user=user, symbol=symbol, shares=shares, price=price, total=buy)

        # update leftover cash
        money_left = money - buy
        db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=money_left, id=user)

        # return to main page
        flash("Bought!")
        return redirect("/")

    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    user = session["user_id"]
    stocks = db.execute("SELECT symbol, shares, price, time FROM portfolio WHERE user=:user", user=user)
    return render_template("history.html", stocks=stocks)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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
    if request.method == "GET":
        return render_template("quote.html")
    elif request.method == "POST":
        if lookup(request.form.get("symbol")) != None:
            symbol = request.form.get("symbol").upper()
            share_price = usd(lookup(symbol).get("price"))
            return render_template("quoted.html", symbol=symbol, share_price=share_price)
        else:
            return apology("Invalid Symbol")
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        # check for input
        if not password:
            return apology("Please input a password")
        elif not username:
            return apology("Please input an username")
        # check password match
        elif password != request.form.get("password2"):
            return apology("Password has to match :(")
        # password has to be at least 5 characters in length
        elif len(password) < 5:
            return (apology("Password needs to be at least 5 characters"))
        # check for unique username
        elif db.execute("SELECT username FROM users WHERE username = :username", username=username):
            return apology("Username is taken")
        # hash passowwrd
        hash_password = generate_password_hash(password)
        # update database with new user
        new_user = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash_password)
        session["user_id"] = new_user
        # notification
        flash("Registered!")
        # go back to main page
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        # check for input
        if not request.form.get("symbol"):
            return apology("missing symbol")
        if not request.form.get("shares"):
            return apology("missing shares")
        # check for valid input
        if float(request.form.get("shares")) < 1:
            return apology("shares cannot be negative")
        user = session["user_id"]
        portfolio = db.execute("SELECT symbol, SUM(shares) AS shares FROM portfolio WHERE user=:user AND symbol=:symbol GROUP BY symbol", user=user, symbol=request.form.get("symbol"))
        if float(portfolio[0]["shares"]) < float(request.form.get("shares")):
            return apology("You do not have that many shares")

        # calculate sell price
        symbol = request.form.get("symbol").upper()
        shares = int(request.form.get("shares"))
        sell = float(lookup(symbol).get("price")) * float(shares)

        # sell
        data = db.execute("SELECT cash FROM users WHERE id = :id", id = user)
        money = data[0]["cash"]
        price = lookup(symbol).get("price")
        db.execute("INSERT INTO portfolio (user, symbol, shares, price, total) VALUES (:user, :symbol, :shares, :price, :total)", user=user, symbol=symbol, shares=-shares, price=price, total=sell)

        # update leftover cash
        money_left = money + sell
        db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=money_left, id=user)

        # return to main page
        flash("Sold!")
        return redirect("/")

    else:
        user = session["user_id"]
        portfolio = db.execute("SELECT * FROM portfolio WHERE user=:user GROUP BY symbol", user=user)
        return render_template("sell.html", portfolio=portfolio)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
