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
DEFAULT_BRANCH = "main"


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


def get_repo_age_commit_based() -> float:
    log.debug('Getting age commit based')
    try:
        commits = list(repo.iter_commits(DEFAULT_BRANCH))
        last_commit_datetime = commits[-1].committed_datetime
    except GitCommandError:
        return 0.0
    age_in_months = round(
            (datetime.datetime.now(datetime.timezone.utc) - last_commit_datetime).days/30,
            2
    )
    return age_in_months


def get_repo_commit_rate() -> float:
    log.debug('Getting commit rate')
    try:
        commits = list(repo.iter_commits(DEFAULT_BRANCH))
    except GitCommandError:
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


def get_repo_metadata(repo: str) -> str:
    log.info(f'Getting Repository Metadata: {repo}')
    age_in_months = get_repo_age_commit_based()
    commit_rate = get_repo_commit_rate()
    return age_in_months, commit_rate


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


def try_build_docker(path: str = '.'):
    log.info(f"Searching for Dockerfiles in {path}")
    paths = get_files_by_regex(regex=r".*Dockerfile*", dir_to_check=path)
    log.debug(f"Found {len(paths)} Dockerfiles")
    image_names = []
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
                log.debug(f"Image syft_image_build:{index} failed to build")
                raise ChildProcessError()
            image_names.append(f"syft_image_build:index{index}")
        except ChildProcessError:
            continue
    return image_names


def get_syft_for_dockerfiles(image_names: list = []):
    log.info("Getting SBOM with syft through Docker")
    components = {'components': []}
    for image in image_names:
        process = subprocess.run(
                f"syft {image} -o cyclonedx-json",
                shell=True,
                capture_output=True
        )
        if process.returncode != 0:
            log.debug("Syft got erorr while reading image, skipping this image")
            raise ChildProcessError()
        process_output = json.loads(process.stdout)
        components['components'] += process_output['components']
    return components


def get_syft_sbom(path: str = '.') -> dict:
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
        image_names = try_build_docker(path)
        process_output = get_syft_for_dockerfiles(image_names)
    return process_output['components']


def compressor(repo: str = '', **kwargs) -> dict:
    age = kwargs.get('age', 0)
    cr = kwargs.get('commit_rate', 0)
    languages = kwargs.get('languages', {})
    packages = kwargs.get(
            'packages',
            [{'type': None, 'name': 'not_a_pkg', 'version': 0.0, 'bom-ref': None}]
    )

    structure = {
        'repo': repo,
        'metadata': {'age': age, 'commit_rate': cr},
        'languages': languages,
        'packages': []
    }

    for pkg in packages:
        try:
            pkg_structure = {
                    'name': pkg['name'],
                    'type': pkg['type'],
                    'version': pkg['version'],
                    'bom-ref': pkg['bom-ref'],
            }
        except KeyError:
            pkg_structure = {
                    'name': pkg['name'],
                    'type': pkg['type'],
                    'version': pkg['version'],
                    'bom-ref': None,
            }
        structure['packages'].append(pkg_structure)
    return structure


def load_to_s3(repo: str, json_data: dict, bucket: str, role: str) -> None:
    s3 = boto3.resource('s3')
    sts = boto3.client('sts')
    assume_role_response = sts.assume_role(
        RoleArn=role,
        RoleSessionName='blackbox-actions',
    )
    json_obj = json.dumps(json_data).encode('UTF-8')
    json_hash = hash(json_obj)
    date = datetime.datetime.now().strftime('%Y-%M-%d')
    s3object = s3.Object(
            bucket,
            f'/tmp/{date}-{repo}-{json_hash}.json'
    )
    s3object.put(
                Body=(bytes())
    )


def load_local(repo: str, json_data: dict) -> None:

    json_obj = json.dumps(json_data).encode('UTF-8')
    json_hash = hash(json_obj)
    date = datetime.datetime.now().strftime('%Y-%M-%d')
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
    age, cr = get_repo_metadata(repo)
    log.info(f"The AGE is: {age}, The CR is: {cr}")
    syft_output = get_syft_sbom('.')
    log.info(f"Found {len(syft_output)} metadatas with syft")
    languages = get_repo_languages(repo)
    log.info(f"This languages where found in the repo: {languages}")
    sbom_data = compressor(
            repo=repo,
            age=age,
            commit_rate=cr,
            languages=languages,
            packages=syft_output,
    )

    load_local(repo, sbom_data)
    load_to_s3(repo, sbom_data, bucket, role)
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
            verbose=verbose
    )


if __name__ == "__main__":

    click_callback()
