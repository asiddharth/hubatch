"""
Useful tools for managing organisations
"""
from .common import BaseController
from connectors.github import GitHubConnector

import parsers
import sys
import datetime

import logging, time

PREFIX = "CS2103JAN2018-"
output_files = ['users_merged', 'users_not_merged']

class TeamProjectMergeStatusDetector(BaseController):
    def __init__(self, cfg):
        self.cfg = cfg

    def setup_argparse(self, subparsers):
        """
        Sets up the subparser for MergeDetector
        """
        parser = subparsers.add_parser('team-project', help='GitHub organisation management tools')
        org_subparsers = parser.add_subparsers(help='name of tool to execute')
        self.setup_check_merge(org_subparsers)


    def setup_check_merge(self, subparsers):
        parser = subparsers.add_parser('check-merge', help='mass invite GitHub users into an organisation')
        parser.add_argument('-csv', type=str,
                            help='filename of the CSV containing a list of GitHub usernames, team affiliations, day')
        parser.add_argument('-s', '--start_date', type=str,
                            help='start checking for merges from a particular timestamp')
        parser.add_argument('-e', '--end_date', type=str,
                            help='Deadline of the merged code')
        parser.add_argument('-d', '--day', type=str,
                            help='Deadline day of the week')
        parser.set_defaults(func=self.check_and_return_unmerged)


    def check_and_return_unmerged(self, args):
        logging.debug('CSV datafile: %s', args.csv)
        if parsers.common.are_files_readable(args.csv):
            users_merged, users_not_merged = self.check_merge_status(args.csv, args.start_date, args.end_date, args.day)
            parsers.csvparser.write_items_to_file([users_merged, users_not_merged], output_files)
            print(users_not_merged, users_merged)
        else:
            sys.exit(1)


    def check_merge_status(self, csv_file, start_date, end_date, day):
        teams_to_check = self.extract_relevant_info(csv_file, day)
        users_not_merged = []
        users_merged = []
        start_datetime = datetime.datetime.strptime(start_date, '%d/%m/%Y')
        end_datetime = datetime.datetime.strptime(end_date, '%d/%m/%Y')

        for team_id, members in teams_to_check.items():
            organization = PREFIX + team_id
            logging.debug('Checking team: %s', organization)
            repository = GitHubConnector(self.cfg.get_api_key(),organization+"/main", organization).repo
            users_merged_in_team, users_not_merged_in_team = self.get_team_merge_info(end_datetime,
                                                                                      members,
                                                                                      repository,
                                                                                      start_datetime)
            users_merged += list(users_merged_in_team)
            users_not_merged += users_not_merged_in_team
        return users_merged, users_not_merged

    def get_team_merge_info(self, end_datetime, members, repository, start_datetime):
        users_merged_in_team = {}
        users_not_merged_in_team = []
        for pull_request in repository.get_pulls(state="closed", sort="updated", direction="desc"):
            if pull_request.closed_at <= end_datetime and pull_request.closed_at >= start_datetime:
                if (pull_request.is_merged()):
                    users_merged_in_team[pull_request.user.login] = 1
        for member in members:
            if member not in users_merged_in_team:
                users_not_merged_in_team.append(member)
        return users_merged_in_team, users_not_merged_in_team

    def extract_relevant_info(self, csv_file, day):
        user_list = parsers.csvparser.get_rows_as_list(csv_file)
        users_to_check = list(map(lambda x: [x[0].split(".")[-1]+"-"+x[1].split(".")[1], x[2]],
                                  filter(lambda x: x[0][-3] == day, user_list)))
        team_list = dict()
        for item in users_to_check :
            existing_members = team_list.get(item[0],[])
            existing_members.append(item[1])
            team_list[item[0]] = existing_members
        return team_list
