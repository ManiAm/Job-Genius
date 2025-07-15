
import os
import getpass
import logging
import inspect

from rest_client import REST_API_Client
import models_redis

log = logging.getLogger(__name__)


class Abstract_Enrich_REST_API_Client(REST_API_Client):

    def __init__(self,
                 url=None,
                 api_ver=None,
                 base=None,
                 user=getpass.getuser()):

        super().__init__(url, api_ver, base, user)

        self.access_token = os.getenv('ABSTRACT_ENRICH_API_KEY', None)


    def enrich_company(self, domain):

        frame = inspect.currentframe()
        cached = models_redis.get_from_cache(frame)
        if cached is not None:
            return True, cached

        url = f"{self.baseurl}"

        params = {
            "api_key": self.access_token,
            "domain": domain
        }

        status, output = self.request("GET", url, params=params, timeout=10)
        if not status:
            return False, output

        models_redis.set_to_cache(frame, output)

        return True, output


if __name__ == "__main__":

    client = Abstract_Enrich_REST_API_Client(url="https://companyenrichment.abstractapi.com", api_ver="v2")

    status, output = client.enrich_company(domain="https://www.cisco.com/")

    bla = 0
