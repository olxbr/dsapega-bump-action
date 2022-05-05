import requests
import logging
import time


class GHAPIRequests():
    def __init__(self, **kwargs):
        self.DEFAULT_SLEEP = kwargs.get("DEFAULT_SLEEP", 0.5)
        self.log = logging.getLogger(__name__)
        self.sleepbase = 2
        self.MAXIMUM_ATTEMPTS = 8  # Aprox 5min

    def get(self, url, **kwargs):
        """Encapsulation of get Method"""
        params = kwargs.get("params")
        headers = kwargs.get("headers")
        attempt = 0
        while attempt <= self.MAXIMUM_ATTEMPTS:
            try:
                self.log.debug("Get and sleep")
                result = requests.get(url, params=params, headers=headers)
                time.sleep(self.DEFAULT_SLEEP)
                if result.status_code == 403:
                    attempt += 1
                    sleeptime = self.sleepbase ** attempt
                    self.log.warning(f"The previous attempt fail. Attempt {attempt}/{self.MAXIMUM_ATTEMPTS} will begin in {sleeptime}s")
                    time.sleep(sleeptime)
                else:
                    return result
            except ConnectionError:
                attempt += 1
                self.log.debug(f"Got ConnectionError. Sleeping for {self.sleepbase}s and retrying")
                time.sleep(sleeptime)
                continue
            
