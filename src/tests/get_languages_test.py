import datetime
import unittest
import boto3
from git import GitCommandError

from unittest.mock import patch
from unittest import mock
from freezegun import freeze_time
from moto import mock_s3, mock_sts

import get_languages_from_repo

import utils as test_utils


class GetLangauges(unittest.TestCase):

    @patch(
            'gh_api_requester.GHAPIRequests.get',
            side_effect=test_utils.mocked_requests_get
    )
    def test_get_repo_languages(self, mock_get):
        repos = get_languages_from_repo.get_repo_languages(repo='tech-radar')
        self.assertEqual(
                repos,
                {
                    "kotlin": '5000',
                    "python": '4000'
                }
        )

    @patch(
            'gh_api_requester.GHAPIRequests.get',
            side_effect=test_utils.mocked_requests_get
    )
    def test_get_repo_return_0_languages(self, mock_get):
        repos = get_languages_from_repo.get_repo_languages(repo='zero-lang-repo')

        self.assertEqual(
                repos,
                {}
        )

    @patch('get_languages_from_repo.repo')
    @freeze_time("2022-05-04")
    def test_get_repo_age_commit_based(self, mock_repo):
        mock_iterable = mock.Mock()
        mock_repo.iter_commits.return_value = [mock_iterable]
        mock_iterable.committed_datetime = datetime.datetime.strptime('2022-04-04 +0000', '%Y-%m-%d %z')

        age = get_languages_from_repo.get_repo_age_commit_based()

        self.assertEqual(age, 1.0)

    @patch('get_languages_from_repo.repo')
    @freeze_time("2022-05-04")
    def test_get_repo_age_commit_basd_clean_tree(self, mock_repo):
        mock_repo.iter_commits.side_effect = GitCommandError('git rev-list master --', 128)

        age = get_languages_from_repo.get_repo_age_commit_based()

        self.assertEqual(age, 0.0)

    @patch('get_languages_from_repo.repo')
    @freeze_time("2022-05-04")
    def test_get_repo_commit_rate(self, mock_repo):
        mock_iterable_list = []
        for i in range(1,10):
            mock_iterable = mock.Mock()
            mock_iterable.committed_datetime = datetime.datetime.strptime(f'2022-04-0{i} +0000', '%Y-%m-%d %z')
            mock_iterable_list.append(mock_iterable)
        mock_repo.iter_commits.return_value = mock_iterable_list

        cr = get_languages_from_repo.get_repo_commit_rate()

        self.assertEqual(cr, 0.3)

    @patch('get_languages_from_repo.repo')
    @freeze_time("2022-05-04")
    def test_get_repo_age_commit_basd_with_clean_tree(self, mock_repo):
        mock_repo.iter_commits.side_effect = GitCommandError('git rev-list master --', 128)

        cr = get_languages_from_repo.get_repo_commit_rate()

        self.assertEqual(cr, 0.0)

    @patch('get_languages_from_repo.repo')
    @freeze_time("2022-05-04")
    def test_get_repo_metadata_with_clean_tree(self, mock_repo):
        mock_repo.iter_commits.side_effect = GitCommandError('git rev-list master --', 128)

        age, cr = get_languages_from_repo.get_repo_metadata('tech-radar')

        self.assertEqual(cr, 0.0)
        self.assertEqual(age, 0.0)

    @patch('get_languages_from_repo.repo')
    @freeze_time("2022-05-01")
    def test_get_repo_metadata(self, mock_repo):
        mock_iterable_list = []
        for i in range(9, 0, -1):
            mock_iterable = mock.Mock()
            mock_iterable.committed_datetime = datetime.datetime.strptime(f'2022-04-0{i} +0000', '%Y-%m-%d %z')
            mock_iterable_list.append(mock_iterable)
        mock_repo.iter_commits.return_value = mock_iterable_list

        age, cr = get_languages_from_repo.get_repo_metadata('tech-radar')

        self.assertEqual(cr, 0.3)
        self.assertEqual(age, 1.0)

    @mock_s3
    @mock_sts
    def test_load_to_s3_with_assume_role(self):
        repo = 'tech-radar'
        json_data = '{"foo": "bar"}'
        bucket = 'blackbox'
        role = 'arn:aws:iam::000000000000:role/blackbox'

        conn = boto3.resource('s3', region_name='us-east-1')
        conn.create_bucket(Bucket='blackbox')

        get_languages_from_repo.load_to_s3(repo, json_data, bucket, role)

    def test_compressor(self):
        expected_output = {
                'repo': 'tech-radar',
                'metadata': {'age': 10.1, 'commit_rate': 3.0},
                'languages': {'python': 1000},
                'packages': [{
                    'name': 'not_a_pkg',
                    'type': 'not_pkg',
                    'version': 0.0,
                    'bom-ref': 'none-ref',
                    }]
        }

        syft_output = [{
                'type': 'not_pkg',
                'name': 'not_a_pkg',
                'version': 0.0,
                'bom-ref': 'none-ref',
        }]
        sbom_data = get_languages_from_repo.compressor(
                repo='tech-radar',
                age=10.1,
                commit_rate=3.0,
                languages={'python': 1000},
                packages=syft_output,
        )

        self.assertDictEqual(sbom_data, expected_output)

    def test_compressor_without_bom_ref(self):
        expected_output = {
                'repo': 'tech-radar',
                'metadata': {'age': 10.1, 'commit_rate': 3.0},
                'languages': {'python': 1000},
                'packages': [{
                    'name': 'not_a_pkg',
                    'type': 'not_pkg',
                    'version': 0.0,
                    'bom-ref': None,
                    }]
        }

        syft_output = [{
                'type': 'not_pkg',
                'name': 'not_a_pkg',
                'version': 0.0,
        }]
        sbom_data = get_languages_from_repo.compressor(
                repo='tech-radar',
                age=10.1,
                commit_rate=3.0,
                languages={'python': 1000},
                packages=syft_output,
        )

        self.assertDictEqual(sbom_data, expected_output)

    def test_get_files_by_regex_recursive_no_parameters_passed(self):
        lis_of_files_as_should_be = [
                'dev.yml',
                'Makefile',
                'src/code.py',
                'src/tests.py',
                'src/config/config.yml',
        ]
        with patch('os.listdir') as mocked_listdir:
            with patch('os.path.isdir') as mocked_isdir:
                mocked_listdir.side_effect = [
                        ['dev.yml', 'Makefile', 'src'],
                        ['code.py', 'tests.py', 'config'],
                        ['config.yml']
                ]
                mocked_isdir.side_effect = [
                        False, False, True,
                        False, False, True,
                        False
                ]

                list_of_files = get_languages_from_repo.get_files_by_regex()

        self.assertEqual(lis_of_files_as_should_be, list_of_files)

    def test_get_files_by_regex_recursive(self):
        lis_of_files_as_should_be = [
                'Dockerfile',
                'src/config/Dockerfile.test',
        ]
        with patch('os.listdir') as mocked_listdir:
            with patch('os.path.isdir') as mocked_isdir:
                mocked_listdir.side_effect = [
                        ['dev.yml', 'Dockerfile', 'src'],
                        ['code.py', 'tests.py', 'config'],
                        ['config.yml', 'Dockerfile.test']
                ]
                mocked_isdir.side_effect = [
                        False, False, True,
                        False, False, True,
                        False, False
                ]

                list_of_files = get_languages_from_repo.get_files_by_regex('.*Dockerfile*')

        self.assertEqual(lis_of_files_as_should_be, list_of_files)
