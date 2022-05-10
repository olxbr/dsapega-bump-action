import argparse
import get_languages_from_repo
import json
import logging
import os

from tqdm.contrib.logging import logging_redirect_tqdm

log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))


def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("-c", "--config", help="Action configs", default="")
    args = parser.parse_args()
    cfg = args.config

    log.info('Getting Configurations')
    configs = json.loads(cfg)
    log.info(f'Found this keys in the config variable {configs.keys()}')

    repo = os.getenv('REPO_NAME', 'no-name')
    log.info(f'REPO: {repo}')
    default_branch = os.getenv('DEFAULT_BRANCH', 'main')
    log.info(f'DEFAULT_BRANCH {default_branch}')

    log.info('The SBOM process will begin')
    get_languages_from_repo.process(
        repo=repo,
        token=configs['token'],
        default_branch=default_branch,
        verbose=False,
        bucket=configs['s3-bucket'],
    )
    log.info('Process finished! Bye :)')


if __name__ == '__main__':
    with logging_redirect_tqdm():
        main()
