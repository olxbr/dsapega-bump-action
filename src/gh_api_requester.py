import requests
import logging
import time
import tqdm

from requests.exceptions import ConnectionError, ConnectTimeout


class GHAPIRequests():
    def __init__(self, **kwargs):
        self.DEFAULT_SLEEP = kwargs.get("DEFAULT_SLEEP", 0.2)
        self.log = logging.getLogger(__name__)
        self.sleepbase = 2
        self.MAXIMUM_ATTEMPTS = 8  # Aprox 5min
        self.pbar = tqdm.tqdm(range(5000), position=1, leave=True)  # Ratelimt

    def get(self, url, **kwargs):
        """Encapsulation of get Method"""
        params = kwargs.get("params")
        headers = kwargs.get("headers")
        attempt = 0
        while attempt <= self.MAXIMUM_ATTEMPTS:
            try:
                self.log.debug("Get and sleep")
                result = requests.get(url, params=params, headers=headers)
                self.rate_limit = int(result.headers['X-RateLimit-Used'])
                self.pbar.set_description(f"Rate Limit {self.DEFAULT_SLEEP}")
                self.pbar.n = self.rate_limit
                self.pbar.update()
                if self.rate_limit < 2000:
                    self.DEFAULT_SLEEP = 0
                elif self.rate_limit < 3000 and self.rate_limit >= 2000:
                    self.DEFAULT_SLEEP = 0.1
                elif self.rate_limit < 4000 and self.rate_limit >= 3000:
                    self.DEFAULT_SLEEP = 0.5
                elif self.rate_limit < 4500 and self.rate_limit >= 4000:
                    self.DEFAULT_SLEEP = 0.7
                elif self.rate_limit < 4550 and self.rate_limit >= 4500:
                    self.DEFAULT_SLEEP = 0.7
                elif self.rate_limit < 5000 and self.rate_limit >= 4550:
                    self.DEFAULT_SLEEP = 2
                time.sleep(self.DEFAULT_SLEEP)
            except (ConnectionError, ConnectTimeout):
                attempt += 1
                sleeptime = self.sleepbase ** attempt
                self.log.warning(f"The previous attempt fail. Attempt {attempt}/{self.MAXIMUM_ATTEMPTS} will begin in {sleeptime}s")
                time.sleep(sleeptime)
                self.log.debug(f"Got ConnectionError. Sleeping for {self.sleepbase}s and retrying")
                time.sleep(sleeptime)
                continue
            if result.status_code != 200:
                if result.status_code == 409:
                    return result
                attempt += 1
                self.log.warning(f"{result.url} returned {result.status_code}")
                sleeptime = self.sleepbase ** attempt
                time.sleep(sleeptime)
                self.log.debug(f"Got Ratelimit. Sleeping for {self.sleepbase}s and retrying")
                time.sleep(sleeptime)
            else:
                return result
        return result
