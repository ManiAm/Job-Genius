
import os
import sys
import getpass
import logging

from rest_client import REST_API_Client
from rate_limiter import RateLimiter, rate_limited

log = logging.getLogger(__name__)


class Finnhub_REST_API_Client(REST_API_Client):

    def __init__(self,
                 url=None,
                 api_ver=None,
                 base=None,
                 user=getpass.getuser(),
                 rate_limit=50,
                 rate_window=60):

        super().__init__(url, api_ver, base, user)

        self.API_KEY = os.getenv('FINNHUB_API_KEY', None)
        if not self.API_KEY:
            log.error("FINNHUB_API_KEY environment variable is missing!")
            sys.exit(1)

        self.rate_limiter = RateLimiter(
            key_prefix="finnhub_api",
            max_requests=rate_limit,
            interval_seconds=rate_window,
            user_id=user
        )


    @rate_limited
    def symbol_lookup(self, query):

        url = f"{self.baseurl}/search"
        params = {"q": query, "token": self.API_KEY}

        status, output = self.request("GET", url, params=params)
        if not status:
            return False, output

        if not isinstance(output, dict):
            return False, f"Unexpected output type: {type(output)}"

        result = output.get("result", [])

        return True, result


    #################
    ##### Stock #####
    #################

    @rate_limited
    def company_profile2(self, symbol):

        url = f"{self.baseurl}/stock/profile2"
        params = {"symbol": symbol, "token": self.API_KEY}

        return self.request("GET", url, params=params)


    @rate_limited
    def company_peers(self, symbol):

        url = f"{self.baseurl}/stock/peers"
        params = {"symbol": symbol, "token": self.API_KEY}

        return self.request("GET", url, params=params)


    @rate_limited
    def company_basic_financials(self, symbol, metric="all"):

        url = f"{self.baseurl}/stock/metric"
        params = {"symbol": symbol, "metric": metric, "token": self.API_KEY}

        return self.request("GET", url, params=params)


    @rate_limited
    def recommendation_trends(self, symbol):

        url = f"{self.baseurl}/stock/recommendation"
        params = {"symbol": symbol, "token": self.API_KEY}

        return self.request("GET", url, params=params)


    ################
    ##### News #####
    ################

    @rate_limited
    def company_news(self, symbol, from_date, to_date):

        url = f"{self.baseurl}/company-news"
        params = {"symbol": symbol, "from": from_date, "to": to_date, "token": self.API_KEY}

        return self.request("GET", url, params=params)


    #################
    ##### Other #####
    #################

    @rate_limited
    def quote(self, symbol):

        url = f"{self.baseurl}/quote"
        params = {"symbol": symbol, "token": self.API_KEY}

        return self.request("GET", url, params=params)
