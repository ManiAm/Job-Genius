
import os
import getpass
import logging
import inspect

from rest_client import REST_API_Client
import models_redis

log = logging.getLogger(__name__)


class Company_Enrich_REST_API_Client(REST_API_Client):

    def __init__(self,
                 url=None,
                 api_ver=None,
                 base=None,
                 user=getpass.getuser()):

        super().__init__(url, api_ver, base, user)

        access_token = os.getenv('COMPANY_ENRICH_API_KEY', None)
        if access_token:
            self.headers['Authorization'] = f'Bearer {access_token}'


    def enrich_company_by_domain(self, domain):

        frame = inspect.currentframe()
        cached = models_redis.get_from_cache(frame)
        if cached is not None:
            return True, cached

        url = f"{self.baseurl}/companies/enrich"

        params = {
            "domain": domain
        }

        status, output = self.request("GET", url, params=params, timeout=10)
        if not status:
            return False, output

        models_redis.set_to_cache(frame, output)

        return True, output


    def enrich_company_by_name(
        self,
        name=None,
        linkedinUrl=None,
        twitterUrl=None,
        facebookUrl=None,
        instagramUrl=None,
        youTubeUrl=None):

        frame = inspect.currentframe()
        cached = models_redis.get_from_cache(frame)
        if cached is not None:
            return True, cached

        url = f"{self.baseurl}/companies/enrich"

        payload = {
            "name": name,
            "linkedinUrl": linkedinUrl,
            "twitterUrl": twitterUrl,
            "facebookUrl": facebookUrl,
            "instagramUrl": instagramUrl,
            "youTubeUrl": youTubeUrl
        }

        status, output = self.request("POST", url, json=payload, timeout=10)
        if not status:
            return False, output

        models_redis.set_to_cache(frame, output)

        return True, output


    def find_similar_companies(self, domain):

        frame = inspect.currentframe()
        cached = models_redis.get_from_cache(frame)
        if cached is not None:
            return True, cached

        url = f"{self.baseurl}/companies/similar"

        payload = {
            "domains": [domain],
            "similarityWeight": 0.8,
            "pageSize": 20,
            "exclude": {
                "domains": [domain]
            },
        }

        status, output = self.request("POST", url, json=payload, timeout=10)
        if not status:
            return False, output

        models_redis.set_to_cache(frame, output)

        return True, output


if __name__ == "__main__":

    client = Company_Enrich_REST_API_Client(url="https://api.companyenrich.com")

    # status, output = client.enrich_company_by_domain(domain="https://www.cisco.com/")
    # status, output = client.enrich_company_by_name(name="cisco")
    status, output = client.find_similar_companies(domain="https://www.cisco.com/")

    bla = 0
