"""
Useful tools for managing TAs
"""
from .common import BaseController
from connectors.github import GitHubConnector

import parsers
import sys
import datetime
import logging, time, re, argparse
from collections import defaultdict

ORGANIZATION = "nus-cs2103-AY1718S2"
REPO_PREFIX = "addressbook-level"

class TADuties(BaseController):
    def __init__(self, cfg):
        self.cfg = cfg

    def setup_argparse(self, subparsers):
        """
        Sets up the subparser for PRDetector
        """
        parser = subparsers.add_parser('TA_duties', help='TA management tools')
        addressbook_subparsers = parser.add_subparsers(help='track reviews of TAs')
        self.setup_check_PR(addressbook_subparsers)

    def setup_check_PR(self, subparsers):

        # example_text = '''example:
        # python main.py addressbook-PR check-PR -csv [path_to_csv] 
        # -l [addressbook_level, e.g 1] -s [start date: dd/m/yyyy] 
        # -e [end date: dd/m/yyyy] -w [week number] -d [day: W,T,F]'''

        parser = subparsers.add_parser('track-TA', help='track review status of TAs in Addressbook')
                                    # ,epilog=example_text,
                                    # ,formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument('-csv', type=str,
                            help='filename of the CSV containing a list of GitHub usernames, day')
        parser.add_argument('-l', '--level', type=str,
                            help='Addressbook level number')
        parser.set_defaults(func=self.track_TA_command)

    def track_TA_command(self, args):
        logging.debug('Tracking non-reviews PRs in Addressbook')
        logging.debug('CSV datafile: %s', args.csv)
        if parsers.common.are_files_readable(args.csv):
            users_PRs = self.check_PR_reviews(args.csv, args.level)
            data_to_print = self.format_data_to_print(users_PRs)
            parsers.csvparser.write_items_to_csv([data_to_print], file_list=['student_PRs_day{}_week{}'.format(args.day, args.week)])
        else:
            sys.exit(1)


    def check_PR_reviews(self, csv_file, level):

        assert(level != None)

        list_of_TAs = self.extract_relevant_info(csv_file)

        repository_name = REPO_PREFIX+str(level)
        repository = GitHubConnector(self.cfg.get_api_key(), ORGANIZATION+"/"+repository_name, ORGANIZATION).repo

        student_PRs = self.get_PR_review_info(students_to_check, repository)

        return student_PRs

    def get_PR_review_info(students_to_check, repository):

        students_PRs = defaultdict(list)
        assignment_prefix = "[W{}".format(str(week))

        for pull_request in repository.get_pulls(state="all", sort="updated", direction="desc"):
            if (pull_request.created_at <= end_datetime) and (pull_request.user.login in students_to_check):
                try:
                    question = re.search('\[W.*?\..*?\]', pull_request.title).group()
                    if question[:3] == assignment_prefix:
                        students_PRs[pull_request.user.login].append(question)

                except AttributeError as error:
                    logging.debug(error)

        return students_PRs

    def extract_relevant_info(self, csv_file):
        user_list = parsers.csvparser.get_rows_as_list(csv_file)

        list_of_TAs = set(map(lambda x: x[4], user_list))
        return list_of_TAs

    def format_data_to_print(self, data):
        '''Formats the input data as per printing format required'''

        data_to_print = []
        for student, PRs in data.items():
            data_to_print.append([student,PRs])
        return data_to_print