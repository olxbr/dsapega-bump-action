import argparse
import os
import json
import get_languages_from_repo

from tqdm.contrib.logging import logging_redirect_tqdm


def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("-c", "--config", help="Action configs", default="")
    args = parser.parse_args()
    cfg = args.config

    configs = json.loads(cfg)

    repo = os.getenv('GITHUB_ACTION_REPOSITORY', 'no-name')
    default_branch = os.getenv('DEFAULT_BRANCH', 'main')

    with logging_redirect_tqdm():
        get_languages_from_repo.process(
            repo=repo,
            token=configs['token'],
            default_branch=default_branch,
            verbose=False,
            bucket=configs['s3-bucket'],
        )


if __name__ == '__main__':
    main()
