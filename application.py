from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from datetime import datetime

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd
app.jinja_env.globals.update(usd=usd, lookup=lookup, int=int)

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["PREFERRED_URL_SCHEME"] = 'https'
app.config["DEBUG"] = False
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    # get user cash total
    result = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    cash = result[0]['cash']

    # pull all transactions belonging to user
    portfolio = db.execute("SELECT stock, quantity FROM portfolio")

    if not portfolio:
        return apology("sorry you have no holdings")

    grand_total = cash

    # determine current price, stock total value and grand total value
    for stock in portfolio:
        price = lookup(stock['stock'])['price']
        total = stock['quantity'] * price
        stock.update({'price': price, 'total': total})
        grand_total += total

    return render_template("index.html", stocks=portfolio, cash=cash, total=grand_total)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure stock symbol and number of shares was submitted
        if (not request.form.get("stock")) or (not request.form.get("shares")):
            return apology("must provide stock symbol and number of shares")

        # ensure number of shares is valid
        if int(request.form.get("shares")) <= 0:
            return apology("must provide valid number of shares (integer)")

        # pull quote from yahoo finance
        quote = lookup(request.form.get("stock"))

        # check is valid stock name provided
        if quote == None:
            return apology("Stock symbol not valid, please try again")

        # calculate cost of transaction
        cost = int(request.form.get("shares")) * quote['price']

        # check if user has enough cash for transaction
        result = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        if cost > result[0]["cash"]:
            return apology("you do not have enough cash for this transaction")

        # update cash amount in users database
        db.execute("UPDATE users SET cash=cash-:cost WHERE id=:id", cost=cost, id=session["user_id"]);

        # add transaction to transaction database
        add_transaction = db.execute("INSERT INTO transactions (user_id, stock, quantity, price, date) VALUES (:user_id, :stock, :quantity, :price, :date)",
            user_id=session["user_id"], stock=quote["symbol"], quantity=int(request.form.get("shares")), price=quote['price'], date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # pull number of shares of symbol in portfolio
        curr_portfolio = db.execute("SELECT quantity FROM portfolio WHERE stock=:stock", stock=quote["symbol"])

        # add to portfolio database
        # if symbol is new, add to portfolio
        if not curr_portfolio:
            db.execute("INSERT INTO portfolio (stock, quantity) VALUES (:stock, :quantity)",
                stock=quote["symbol"], quantity=int(request.form.get("shares")))

        # if symbol is already in portfolio, update quantity of shares and total
        else:
            db.execute("UPDATE portfolio SET quantity=quantity+:quantity WHERE stock=:stock",
                quantity=int(request.form.get("shares")), stock=quote["symbol"]);

        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""

    # pull all transactions belonging to user
    portfolio = db.execute("SELECT stock, quantity, price, date FROM transactions WHERE user_id=:id", id=session["user_id"])

    if not portfolio:
        return apology("sorry you have no transactions on record")

    return render_template("history.html", stocks=portfolio)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # clear portfolio for current user
        db.execute("DELETE from portfolio")

        # pull all transactions belonging to user and load into portfolio db
        portfolio = db.execute("SELECT stock, SUM(quantity) AS quantity FROM transactions WHERE user_id=:user_id GROUP BY stock ORDER BY stock", user_id=session["user_id"])

        # if portfolio is empty, return to index
        if portfolio:
            for stock in portfolio:
                # calculate current cost of stock
                symbol = stock['stock']
                quantity = stock['quantity']

                db.execute("INSERT INTO portfolio (stock, quantity) VALUES (:stock, :quantity)", stock=symbol, quantity=quantity)

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure name of stock was submitted
        if not request.form.get("stock"):
            return apology("must provide stock symbol")

        # pull quote from yahoo finance
        quote = lookup(request.form.get("stock"))

        # check is valid stock name provided
        if quote == None:
            return apology("Stock symbol not valid, please try again")

        # stock name is valid
        else:
            return render_template("quoted.html", quote=quote)

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password and password confirmation were submitted
        elif not request.form.get("password") or not request.form.get("password_confirm"):
            return apology("must provide password")

        # ensure password and password confirmation match
        elif request.form.get("password") != request.form.get("password_confirm"):
            return apology("password and password confirmation must match")

        # hash password
        hash = pwd_context.hash(request.form.get("password"))

        # add user to database
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"), hash=hash)

        # ensure username is unique
        if not result:
            return apology("username is already registered")

        # remember which user has logged in
        session["user_id"] = result

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure stock symbol and number of shares was submitted
        if (not request.form.get("stock")) or (not request.form.get("shares")):
            return apology("must provide stock symbol and number of shares")

        # ensure number of shares is valid
        if int(request.form.get("shares")) <= 0:
            return apology("must provide valid number of shares (integer)")

        available = db.execute("SELECT quantity FROM portfolio WHERE :stock=stock", stock=request.form.get("stock"))

        # check that number of shares being sold does not exceed quantity in portfolio
        if int(request.form.get("shares")) > available[0]['quantity']:
            return apology("You may not sell more shares than you currently hold")

        # pull quote from yahoo finance
        quote = lookup(request.form.get("stock"))

        # check is valid stock name provided
        if quote == None:
            return apology("Stock symbol not valid, please try again")

        # calculate cost of transaction
        cost = int(request.form.get("shares")) * quote['price']

        # update cash amount in users database
        db.execute("UPDATE users SET cash=cash+:cost WHERE id=:id", cost=cost, id=session["user_id"]);

        # add transaction to transaction database
        add_transaction = db.execute("INSERT INTO transactions (user_id, stock, quantity, price, date) VALUES (:user_id, :stock, :quantity, :price, :date)",
            user_id=session["user_id"], stock=quote["symbol"], quantity=-int(request.form.get("shares")), price=quote['price'], date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # update quantity of shares and total
        db.execute("UPDATE portfolio SET quantity=quantity-:quantity WHERE stock=:stock",
            quantity=int(request.form.get("shares")), stock=quote["symbol"]);

        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        # pull all transactions belonging to user
        portfolio = db.execute("SELECT stock FROM portfolio")

        return render_template("sell.html", stocks=portfolio)
