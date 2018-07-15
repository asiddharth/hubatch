"""
Useful tools for managing addressbook (Phase A) activities
"""
from .common import BaseController
from connectors.github import GitHubConnector

import parsers
import sys
import datetime
import logging, time, re
from collections import defaultdict

ORGANIZATION = "nus-cs2103-AY1718S2"
REPO_PREFIX = "addressbook-level"

class AddressbookPRDetector(BaseController):
    def __init__(self, cfg):
        self.cfg = cfg

    def setup_argparse(self, subparsers):
        """
        Sets up the subparser for PRDetector
        """
        print("Organization for PR checking (Phase A): ", ORGANIZATION)
        parser = subparsers.add_parser('addressbook-PR', help='GitHub Addressbook management tools')
        addressbook_subparsers = parser.add_subparsers(help='name of tool to execute')
        self.setup_check_PR(addressbook_subparsers)

    def setup_check_PR(self, subparsers):

        parser = subparsers.add_parser('check-PR', help='check submitted PRs of students in Addressbook')
        parser.add_argument('-csv', type=str,
                            help='filename of the CSV containing a list of GitHub usernames, day')
        parser.add_argument('-l', '--level', type=str,
                            help='Addressbook level number')
        parser.add_argument('-s', '--start_date', type=str,
                            help='start checking for PR submission from this date onwards')
        parser.add_argument('-e', '--end_date', type=str,
                            help='Deadline date of the PR submission')
        parser.add_argument('-w', '--week', type=int,
                            help='Week number of the course')
        parser.add_argument('-d', '--day', type=str,
                            help='Deadline day of the week')
        parser.set_defaults(func=self.check_and_return_no_PRs)


    def check_and_return_no_PRs(self, args):
        
        logging.debug('CSV datafile: %s', args.csv)
        if parsers.common.are_files_readable(args.csv):
            users_PRs = self.check_PR_status(args.csv, args.level, args.start_date, args.end_date, args.week, args.day)
            data_to_print = self.format_data_to_print(users_PRs)
            parsers.csvparser.write_items_to_csv([data_to_print], file_list=['student_PRs_day{}_week{}'.format(args.day, args.week)])
        else:
            sys.exit(1)


    def check_PR_status(self, csv_file, level, start_date, end_date, week, day):

        assert(level != None)

        students_to_check = self.extract_relevant_info(csv_file, day)
        start_datetime = datetime.datetime.strptime(start_date, '%d/%m/%Y')
        end_datetime = datetime.datetime.strptime(end_date, '%d/%m/%Y')

        repository_name = REPO_PREFIX+str(level)
        repository = GitHubConnector(self.cfg.get_api_key(), ORGANIZATION+"/"+repository_name, ORGANIZATION).repo

        student_PRs = self.get_student_PR_info(end_datetime, students_to_check, repository, start_datetime, week)

        return student_PRs

    def get_student_PR_info(self, end_datetime, students_to_check, repository, start_datetime, week):

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

    def extract_relevant_info(self, csv_file, day):
        user_list = parsers.csvparser.get_rows_as_list(csv_file)

        users_to_check = list(map(lambda x: x[2],
                                  filter(lambda x: x[0][-3] == day, user_list)))
        
        return users_to_check

    def format_data_to_print(self, data):
        '''Formats the input data as per printing format required'''

        data_to_print = []
        for student, PRs in data.items():
            data_to_print.append([student,PRs])
        return data_to_print