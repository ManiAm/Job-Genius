
import os
import getpass
import logging
import inspect
import time

from rest_client import REST_API_Client
import models_redis

log = logging.getLogger(__name__)


class JSearch_REST_API_Client(REST_API_Client):

    def __init__(self,
                 url=None,
                 api_ver=None,
                 base=None,
                 user=getpass.getuser()):

        super().__init__(url, api_ver, base, user)

        self.headers['x-rapidapi-host'] = 'jsearch.p.rapidapi.com'

        access_token = os.getenv('RAPID_API_KEY', None)
        if access_token:
            self.headers['x-rapidapi-key'] = access_token


    def job_search(
        self,
        keywords,
        location=None,
        country="us",
        language="en",
        date_posted="all",
        work_from_home=False,
        employment_types=None,
        job_requirements=None,
        radius=None,
        exclude_job_publishers=None,
        fields=None,
        page_num=1,
        num_pages=10,
        timeout=10):
        """
        Search for jobs using the external job search API with optional filters.

        Parameters:
            keywords (str): Search keywords (e.g., "software engineer", "data analyst").
            location (str, optional): Location to search within (e.g., "Berlin", "California").
            country (str, optional): ISO 3166-1 alpha-2 country code (default is 'us').
            language (str, optional): ISO 639-1 language code (optional).
            date_posted (str, optional): Filter jobs by post date. Options: 'all', 'today', '3days', 'week', 'month'. Default is 'all'.
            work_from_home (bool, optional): If True, include only remote jobs.
            employment_types (str, optional): Comma-separated list of employment types. Options: FULLTIME, PARTTIME, CONTRACTOR, INTERN.
            job_requirements (str, optional): Comma-separated list of requirements. Options: under_3_years_experience, more_than_3_years_experience, no_experience, no_degree.
            radius (int, optional): Distance in kilometers from location (used with query).
            exclude_job_publishers (str, optional): Comma-separated list of job publishers to exclude (e.g., 'Indeed,Dice').
            fields (str, optional): Comma-separated list of fields to include in the response (e.g., 'employer_name,job_title').
            num_pages (int, optional): Number of pages to request per API call. Each page includes up to 10 results. Default is 10.
        """

        frame = inspect.currentframe()
        cached = models_redis.get_from_cache(frame)
        if cached is not None:
            return True, cached

        query = keywords

        if location:
            query += f" in {location}"

        params = {
            "query": query.strip(),  # Free-form job search query
            "country": country,
            "language": language,
            "date_posted": date_posted,
            "page": page_num,
            "num_pages": num_pages
        }

        if work_from_home:
            params["work_from_home"] = "true"
        if employment_types:
            params["employment_types"] = employment_types
        if job_requirements:
            params["job_requirements"] = job_requirements
        if radius:
            params["radius"] = radius
        if exclude_job_publishers:
            params["exclude_job_publishers"] = exclude_job_publishers
        if fields:
            params["fields"] = fields

        url = f"{self.baseurl}/search"

        print(f"query used: {params}")

        start_time = time.perf_counter()

        status, output = self.request("GET", url, params=params, timeout=timeout)

        elapsed = time.perf_counter() - start_time
        print(f"[DEBUG] Query took {elapsed:.2f} seconds")

        if not status:
            return False, output

        result_status = output.get("status", None)
        if result_status and result_status != "OK":
            return False, "job_search failed"

        data_list = output.get("data", [])

        models_redis.set_to_cache(frame, data_list, ttl=5*60*60)  ## TODO: remove this later

        return True, data_list


    def job_details(self):

        pass


    def job_salary(self):

        pass
