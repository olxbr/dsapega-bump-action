import argparse
import get_languages_from_repo
import json
import logging
import os


log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))


def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("-c", "--config", help="Action configs", default="")
    args = parser.parse_args()
    cfg = args.config

    log.info("Getting Configurations")
    configs = json.loads(cfg)
    log.info(f"Found this keys in the config variable {configs.keys()}")

    repo = os.getenv("REPO_NAME", "no-name")
    log.info(f"REPO: {repo}")

    default_branch = os.getenv("DEFAULT_BRANCH", "main")
    log.info(f"DEFAULT_BRANCH: {default_branch}")

    docker_token = os.getenv("DOCKER_ECR_PASSWORD", "")
    log.info("DOCKER TOKEN STATUS: acquired")

    docker_registry = os.getenv("DOCKER_REGISTRY", "")
    log.info("DOCKER REGISTRY STATUS: acquired")

    access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "")
    secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    log.info("AWS KEYS: acquired")

    log.info("DOCKER TOKEN STATUS: acquired")

    log.info("The SBOM process will begin")
    get_languages_from_repo.process(
        repo=repo,
        token=configs["token"],
        default_branch=default_branch,
        verbose=False,
        bucket=configs["s3-bucket"],
        role=configs["s3-role-arn"],
        external_id=configs["s3-role-external-id"],
        docker_token=docker_token,
        docker_registry=docker_registry,
        access_key_id=access_key_id,
        secret_access_Key=secret_access_key,
    )
    log.info("Process finished! Bye :)")


if __name__ == "__main__":
    main()
