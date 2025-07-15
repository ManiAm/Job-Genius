
import os
import sys
import getpass
import logging

from rest_client import REST_API_Client

log = logging.getLogger(__name__)


class Finnhub_REST_API_Client(REST_API_Client):

    def __init__(self,
                 url=None,
                 api_ver=None,
                 base=None,
                 user=getpass.getuser()):

        super().__init__(url, api_ver, base, user)

        self.API_KEY = os.getenv('FINNHUB_API_KEY', None)
        if not self.API_KEY:
            log.error("FINNHUB_API_KEY environment variable is missing!")
            sys.exit(1)


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

    def company_profile2(self, symbol):

        url = f"{self.baseurl}/stock/profile2"
        params = {"symbol": symbol, "token": self.API_KEY}

        return self.request("GET", url, params=params)


    def company_peers(self, symbol):

        url = f"{self.baseurl}/stock/peers"
        params = {"symbol": symbol, "token": self.API_KEY}

        return self.request("GET", url, params=params)


    def company_basic_financials(self, symbol, metric="all"):

        url = f"{self.baseurl}/stock/metric"
        params = {"symbol": symbol, "metric": metric, "token": self.API_KEY}

        return self.request("GET", url, params=params)


    def recommendation_trends(self, symbol):

        url = f"{self.baseurl}/stock/recommendation"
        params = {"symbol": symbol, "token": self.API_KEY}

        return self.request("GET", url, params=params)


    ################
    ##### News #####
    ################

    def company_news(self, symbol, from_date, to_date):

        url = f"{self.baseurl}/company-news"
        params = {"symbol": symbol, "from": from_date, "to": to_date, "token": self.API_KEY}

        return self.request("GET", url, params=params)


    #################
    ##### Other #####
    #################

    def quote(self, symbol):

        url = f"{self.baseurl}/quote"
        params = {"symbol": symbol, "token": self.API_KEY}

        return self.request("GET", url, params=params)
