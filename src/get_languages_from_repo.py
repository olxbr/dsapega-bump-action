import boto3
import click
import datetime
import json
import logging
import os
import re
import subprocess

from git import Repo, GitCommandError

from gh_api_requester import GHAPIRequests

log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

requester = GHAPIRequests()
repo = Repo()

TOKEN = os.getenv('GH_TOKEN', '')
INTERVAL = 180  # Three months
COMMIT_RATE_INTERVAL = 30  # Calculate commit rate per month
BASE_URL = "https://api.github.com"


def get_repo_languages(repo: str) -> dict:
    log.debug(f'Getting {repo} languages')
    response = requester.get(
                BASE_URL + f"/repos/olxbr/{repo}/languages",
                headers={
                    'Authorization': f"token {TOKEN}",
                    'Accept': 'application/vnd.github.v3+json',
                },
    )
    data = response.json()
    try:
        most_used = list(data.keys())[0]
        log.info(f'The most used language for {repo} is {most_used}')
    except IndexError:
        log.debug(f'No languages found for repo {repo}')
    return data


def get_creation_date(repo: str) -> str:
    log.debug(f"Getting {repo} creation date")
    response = requester.get(
        BASE_URL + f"/repos/olxbr/{repo}",
        headers={
            "Authorization": f"token {TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    data = response.json()
    return data["created_at"]


def get_repo_age_metadata_commit_based(default_branch: str = "main") -> float:
    log.debug(f"Getting age commit based... branch: {default_branch}")
    try:
        commits = list(repo.iter_commits(default_branch, all=True))
        first_commit_datetime = commits[-1].committed_datetime
        last_commit_datetime = commits[-1].committed_datetime
        first_commit_str = first_commit_datetime.strftime("%Y-%m-%d %z")
        last_commit_str = last_commit_datetime.strftime("%Y-%m-%d %z")
    except GitCommandError:
        log.warning(f'Failed to get age! Using default 0.0 (branch: {default_branch})')
        return 0.0
    age_in_months = round(
            (datetime.datetime.now(datetime.timezone.utc) - last_commit_datetime).days/30,
            2
    )
    return age_in_months, first_commit_str, last_commit_str


def get_repo_commit_rate(default_branch: str = 'main') -> float:
    log.debug(f'Getting commit rate... branch: {default_branch}')
    try:
        commits = list(repo.iter_commits(default_branch))
    except GitCommandError:
        log.warning(f'Failed to get CR! Using default 0.0 (branch: {default_branch})')
        return 0.0
    conter = 0
    month_ago = (
                datetime.datetime.now(datetime.timezone.utc) -
                datetime.timedelta(days=INTERVAL)
    )
    for commit in commits:
        if commit.committed_datetime > month_ago:
            conter += 1

    return conter / COMMIT_RATE_INTERVAL


def get_repo_metadata(repo: str, default_branch: str) -> str:
    log.info(f"Getting Repository Metadata: {repo}:{default_branch}")
    (
        age_in_months,
        first_commit_date,
        last_commit_date,
    ) = get_repo_age_metadata_commit_based(default_branch)
    creation_date = get_creation_date(repo)
    commit_rate = get_repo_commit_rate(default_branch)
    return age_in_months, commit_rate, creation_date


def get_files_by_regex(regex: str = r"(.*?)", dir_to_check: str = "."):
    """Return any file in the directory with Regex Match"""
    r = re.compile(regex)
    files = []
    directoryes = []
    try:
        files = os.listdir(dir_to_check)
    except FileNotFoundError:
        return files
    for f in files:
        if os.path.isdir(os.path.join(dir_to_check, f)):
            directoryes.append(f)
    for directory in directoryes:
        files_in_dir = get_files_by_regex(
                dir_to_check=f"{dir_to_check}/{directory}"
        )
        for workflow in files_in_dir:
            files.append(f"{directory}/{workflow}")
        files.remove(directory)
    filtered_files = list(filter(r.match, files))
    return filtered_files


def login_in_docker(token: str, registry: str) -> None:
    log.info(f"Loging in {registry}")
    try:
        log.debug("Trying docker login")
        process = subprocess.run(
                f'echo "{token}" | docker login --username AWS --password-stdin {registry}',
                shell=True,
                capture_output=True
        )
        if process.returncode != 0:
            log.warning("Failed to login in the docker registry")
            raise ChildProcessError()
        log.debug("Login in docker successfull")
    except ChildProcessError:
        return None


def try_build_docker(path: str = '.', **kwargs) -> list:
    log.info(f"Searching for Dockerfiles in {path}")
    token = kwargs.get('docker_token', '')
    registry = kwargs.get('docker_registry', '')
    paths = get_files_by_regex(regex=r".*Dockerfile*", dir_to_check=path)
    log.debug(f"Found {len(paths)} Dockerfiles")
    image_names = []
    login_in_docker(token, registry)
    for index, dockerfile_file in enumerate(paths):
        try:
            log.debug(f"Building image from path: {path}")
            process = subprocess.run(
                    f"cd {path} && docker build -f {dockerfile_file} -t syft_image_build:index{index} .",
                    shell=True,
                    capture_output=True
            )
            log.debug(f"Image syft_image_build:{index} successfully built")
            if process.returncode != 0:
                log.warning(f"Image syft_image_build:{index} failed to build")
                raise ChildProcessError()
            image_names.append(f"syft_image_build:index{index}")
        except ChildProcessError:
            continue
    return image_names


def get_syft_for_dockerfiles(image_names: list = []):
    log.info("Getting SBOM with syft through Docker")
    components = {'components': []}
    for image in image_names:
        log.debug(f"Running syft against: {image}")
        process = subprocess.run(
                f"syft {image} -o cyclonedx-json",
                shell=True,
                capture_output=True
        )
        if process.returncode != 0:
            log.warning("Syft got erorr while reading image, skipping this image")
            raise ChildProcessError()
        process_output = json.loads(process.stdout)
        components['components'] += process_output['components']
    return components


def get_syft_sbom(path: str = '.', **kwargs) -> dict:
    log.info("Getting SBOM with syft")
    process = subprocess.run(
            f"syft {path} -o cyclonedx-json",
            shell=True,
            capture_output=True
    )
    if process.returncode != 0:
        log.debug("Syft got erorr while reading image, skipping this image")
        raise ChildProcessError()
    process_output = json.loads(process.stdout)
    try:
        process_output['components'][0]
        if len(process_output['components']) < 10:
            raise IndexError
    except IndexError:
        log.warning("SBOM with syft failed new attempt with docker will start soon")
        image_names = try_build_docker(path, **kwargs)
        process_output = get_syft_for_dockerfiles(image_names)
    return process_output['components']


def compressor(repo: str = "", **kwargs) -> dict:
    log.info("Compressing data in a json objetc")
    age = kwargs.get("age", 0)
    cr = kwargs.get("commit_rate", 0)
    languages = kwargs.get("languages", {})
    created_at = kwargs.get("created_at", None)
    frist_commit_date = kwargs.get("first_commit_date", None)
    last_commit_date = kwargs.get("last_commit_date", None)
    packages = kwargs.get(
            'packages',
            [{'type': None, 'name': 'not_a_pkg', 'version': None, 'bom-ref': None}]
    )

    structure = {
        "repo": repo,
        "metadata": {
            "age": age,
            "commit_rate": cr,
            "created_at": created_at,
            "first_commit_date": frist_commit_date,
            "last_commit_date": last_commit_date,
        },
        "languages": languages,
        "packages": [],
    }

    for pkg in packages:
        try:
            log.debug(f"Found {pkg['name']}:{pkg['type']}")
            pkg_structure = {
                "name": pkg["name"],
                "type": pkg["type"],
                "version": pkg["version"],
                "bom-ref": pkg["bom-ref"],
            }
        except KeyError:
            log.warning(f"The pkg {pkg['name']}:{pkg['type']} does not have a version or bom-ref")
            pkg_structure = {
                "name": pkg["name"],
                "type": pkg["type"],
                "version": None,
                "bom-ref": None,
            }
        structure['packages'].append(pkg_structure)
    return structure


def load_to_s3(repo: str, json_data: dict, bucket: str, role: str, ext_id: str) -> None:
    log.info(f'Sendig SBOM to S3 to the bucket {bucket}')
    sts = boto3.client('sts')
    assume_role_response = sts.assume_role(
        RoleArn=role,
        RoleSessionName='blackbox-actions',
        ExternalId=ext_id,
    )
    log.debug('Getting new credentials through sts:assumeRole')
    credentials = assume_role_response['Credentials']
    s3 = boto3.resource(
        's3',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
    )
    log.debug('Converting and sending object')
    json_obj = json.dumps(json_data).encode('UTF-8')
    json_hash = hash(json_obj)
    date = datetime.datetime.now().strftime('%Y-%M-%d')
    s3object = s3.Object(
            bucket,
            f'/tmp/{date}-{repo}-{json_hash}.json'
    )
    s3object.put(
                Body=(json_obj)
    )
    log.debug('Sending process finished')


def load_local(repo: str, json_data: dict) -> None:
    json_obj = json.dumps(json_data).encode('UTF-8')
    json_hash = hash(json_obj)
    date = datetime.datetime.now().strftime('%Y-%M-%d')
    log.debug(f'Saving local file (/tmp/{date}-{repo}-{json_hash}.json)')
    with open(f"/tmp/{date}-{repo}-{json_hash}.json", "w+", encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)


def process(repo: str, token: str, default_branch: str, role: str, verbose: bool, **kwargs):
    global TOKEN

    bucket = kwargs.get('bucket', 'devtools-test')
    if verbose:
        logging.basicConfig(level=os.environ.get("LOGLEVEL", "DEBUG"))
    else:
        logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

    TOKEN = token
    age, cr = get_repo_metadata(repo, default_branch)
    log.info(f"The AGE is: {age}, The CR is: {cr}")
    syft_output = get_syft_sbom('.', **kwargs)
    log.info(f"Found {len(syft_output)} metadatas with syft")
    languages = get_repo_languages(repo)
    log.info(f"This languages where found in the repo: {languages}")
    sbom_data = compressor(
        repo=repo,
        age=age,
        commit_rate=cr,
        languages=languages,
        packages=syft_output,
        created_at=created_at,
    )
    log.info("Sbom acquire process finished! Sending...")
    ext_id = kwargs.get('external_id', '')
    load_local(repo, sbom_data)
    load_to_s3(repo, sbom_data, bucket, role, ext_id)
    log.info("Sbom proces finished! That's all folks")
    return sbom_data


@click.command()
@click.option('--repo', help='The repository')
@click.option('--token', help='The gh token')
@click.option('--default_branch', help='The default_branch')
@click.option('--verbose', default=False, help='The default_branch')
def click_callback(repo: str = '', token: str = '', default_branch: str = 'main', verbose: bool = True):
    process(
            repo=repo,
            token=TOKEN,
            default_branch=default_branch,
            verbose=verbose,
    )


if __name__ == "__main__":

    click_callback()
