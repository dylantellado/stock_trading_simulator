import csv
import datetime
import pytz
import requests
import subprocess
import urllib
import uuid

from flask import redirect, render_template, session
from functools import wraps

import time

def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


# def lookup(symbol):
#     """Look up quote for symbol."""

#     # Prepare API request
#     symbol = symbol.upper()
#     end = datetime.datetime.now(pytz.timezone("US/Eastern"))
#     start = end - datetime.timedelta(days=7)

#     # Yahoo Finance API
#     url = (
#         f"https://query1.finance.yahoo.com/v7/finance/download/{urllib.parse.quote_plus(symbol)}"
#         f"?period1={int(start.timestamp())}"
#         f"&period2={int(end.timestamp())}"
#         f"&interval=1d&events=history&includeAdjustedClose=true"
#     )

    # # Query API
    # try:
    #     response = requests.get(
    #         url,
    #         cookies={"session": str(uuid.uuid4())},
    #         headers={"User-Agent": "python-requests", "Accept": "*/*"},
    #     )
    #     response.raise_for_status()

    #     # CSV header: Date,Open,High,Low,Close,Adj Close,Volume
    #     quotes = list(csv.DictReader(response.content.decode("utf-8").splitlines()))
    #     quotes.reverse()
    #     price = round(float(quotes[0]["Adj Close"]), 2)
    #     return {"name": symbol, "price": price, "symbol": symbol}
    # except (requests.RequestException, ValueError, KeyError, IndexError):
    #     return None


def lookup(symbol):
    """Look up quote for symbol."""

    # Prepare API request
    symbol = symbol.upper()
    end = datetime.datetime.now(pytz.timezone("US/Eastern"))
    start = end - datetime.timedelta(days=7)

    # Yahoo Finance API
    url = (
        f"https://query1.finance.yahoo.com/v7/finance/download/{urllib.parse.quote_plus(symbol)}"
        f"?period1={int(start.timestamp())}"
        f"&period2={int(end.timestamp())}"
        f"&interval=1d&events=history&includeAdjustedClose=true"
    )

    # Query API with retry mechanism
    attempts = 3  # Reduce the number of attempts
    backoff_time = 10  # Initial backoff time in seconds
    for attempt in range(attempts):
        try:
            response = requests.get(
                url,
                cookies={"session": str(uuid.uuid4())},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
                    "Accept": "*/*",
                },
            )
            response.raise_for_status()

            # CSV header: Date,Open,High,Low,Close,Adj Close,Volume
            quotes = list(csv.DictReader(response.content.decode("utf-8").splitlines()))

            if not quotes:
                return None

            quotes.reverse()
            price = round(float(quotes[0]["Adj Close"]), 2)
            return {"name": symbol, "price": price, "symbol": symbol}
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                print(f"Rate limit exceeded. Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)  # Increase the delay before the next retry
                backoff_time *= 2  # Exponential backoff
            elif response.status_code == 403:
                print("Access forbidden. Check if the API requires authentication or if the IP is banned.")
                break
            elif response.status_code == 404:
                print("Data not found. Check the symbol and try again.")
                break
            else:
                print(f"HTTP error occurred: {e}")
                break
        except requests.RequestException as e:
            print(f"Request error occurred: {e}")
            break
        except (ValueError, KeyError, IndexError) as e:
            print(f"Data processing error: {e}")
            break
    return None

def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"
