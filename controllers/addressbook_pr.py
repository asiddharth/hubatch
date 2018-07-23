"""
Useful tools for managing addressbook (Phase A) activities
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
REVIEWED_LABELS = ['Reviewed', 'Kudos', 'ReviewedInTutorial', 'AcceptedWithMinimalReview']

class AddressbookPRDetector(BaseController):
    def __init__(self, cfg):
        self.cfg = cfg

    def setup_argparse(self, subparsers):
        """
        Sets up the subparser for PRDetector
        """
        print("Organization for PR checking (Phase A): ", ORGANIZATION)
        parser = subparsers.add_parser('addressbook-PR', help='GitHub Addressbook management tools')
        addressbook_subparsers = parser.add_subparsers(help='check PR submissions')
        self.setup_check_PR(addressbook_subparsers)

    def setup_check_PR(self, subparsers):

        example_text = '''example:
        python main.py addressbook-PR check-PR -csv [path_to_csv] 
        -l [addressbook_level, e.g 1] -s [start date: dd/m/yyyy] 
        -e [end date: dd/m/yyyy] -w [week number] -d [day: W,T,F] '''

        parser = subparsers.add_parser('check-PR', help='check submitted PRs of students in Addressbook'
                                    ,epilog=example_text
                                    ,formatter_class=argparse.RawDescriptionHelpFormatter)
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
            users_PRs_done=self.check_PR_status(args.csv, args.level, args.start_date, 
                                                                      args.end_date, args.week, args.day)
            data_to_print_done = self.format_data_to_print(users_PRs_done)
            parsers.csvparser.write_items_to_csv([data_to_print_done],
                                                  file_list=['student_PRs_done_week{}_AB{}_day{}'.format(args.week, args.level, args.day)], 
                                                             week=args.week, level=args.level)
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
        self.set_consistent_PR_labels(student_PRs)

        for student in students_to_check:
            if student not in student_PRs.keys():
                student_PRs[student] = []

        # student_PRs_done,student_PRs_not_done  = self.filter_by_checklist(student_PRs, students_to_check, checklist)
        return student_PRs

    def set_consistent_PR_labels(self, student_PRs):

        for student, list_of_PRs in student_PRs.items():
            student_PRs[student] = [PR_tag.lower() for PR_tag in list_of_PRs ]

    def get_student_PR_info(self, end_datetime, students_to_check, repository, start_datetime, week):

        students_PRs = defaultdict(list)
        assignment_prefix = "[W{}".format(str(week))

        for pull_request in repository.get_pulls(state="all", sort="updated", direction="desc"):
            if (pull_request.created_at <= end_datetime) and (pull_request.user.login in students_to_check):
                try:
                    question = re.search('\[(W|w).*?\..*?\]', pull_request.title).group()
                    if question[:3] == assignment_prefix:
                        students_PRs[pull_request.user.login].append(question)

                except AttributeError as error:
                    logging.debug(error)

        return students_PRs


    def check_reviewed(self, labels):
        for label in labels :
            if label.name in REVIEWED_LABELS :
                return True
        return False


    def extract_relevant_info(self, csv_file, day):
        user_list = parsers.csvparser.get_rows_as_list(csv_file)

        users_to_check = list(map(lambda x: x[2],
                                  filter(lambda x: x[0][-3] == day, user_list)))
        
        return users_to_check

    def parse_checklist(self, checklist_str):
        checklist = checklist_str.split(",")
        checklist = [PR_tag.lower() for PR_tag in checklist]
        return set(checklist)

    def filter_by_checklist(self, student_PRs, students_to_check, checklist):
        student_PRs_done = dict()
        student_PRs_not_done = dict()

        for student,done_list in student_PRs.items() :
            not_done = checklist - set(done_list)
            done = list(checklist - not_done)
            not_done =  list(not_done)
            student_PRs_done[student] = done
            student_PRs_not_done[student] = not_done

        for student in students_to_check:
            if student not in student_PRs_done.keys():
                student_PRs_done[student] = []
                student_PRs_not_done[student] =list(checklist)

        return student_PRs_done, student_PRs_not_done

    def format_data_to_print(self, data):
        '''Formats the input data as per printing format required'''

        data_to_print = []
        for student, PRs in data.items():
            data_to_print.append([student,PRs])
        return data_to_print