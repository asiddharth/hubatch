"""
Useful tools for managing organisations
"""
from .common import BaseController
from connectors.ghapi import GHAPI

from github import Github, GithubException
import parsers
import requests

import logging, time
from collections import defaultdict
import sys

TEAM = "2851145"

class OrganisationController(BaseController):
    def __init__(self, ghc, cfg):
        self.ghc = ghc
        self.cfg=cfg

    def setup_argparse(self, subparsers):
        """
        Sets up the subparser for issue blaster
        """
        parser = subparsers.add_parser('orgs', help='GitHub organisation management tools')
        org_subparsers = parser.add_subparsers(help='name of tool to execute')
        self.setup_mass_add(org_subparsers)

    def setup_mass_add(self, subparsers):
        parser = subparsers.add_parser('mass-add', help='mass invite GitHub users into an organisation')
        parser.add_argument('-csv', metavar='csv', type=str,
                            help='filename of the CSV containing a list of GitHub usernames')
        parser.add_argument('-s', '--start-from', metavar='username', type=str,
                            help='start adding from a particular user (inclusive) in the CSV')
        # parser.add_argument('-t', '--team', metavar='team-id', type=int,
        #                     help='invites user to the particular team')
        parser.set_defaults(func=self.mass_add_command)

    def mass_add_command(self, args):
        logging.debug('Adding users to organisation')
        logging.debug('User CSV file: %s', args.csv)

        if parsers.common.are_files_readable(args.csv):
            self.add_users_from_csv(args.csv, args.start_from, TEAM)
        else:
            sys.exit(1)

    def add_users_from_csv(self, csv_file, start_from, teamid):

        teams_to_check, student_details=self.extract_team_info(csv_file)
        
        users = []
        for team, students in teams_to_check.items():
            users+=students
        user_list = sorted(users)

        if start_from and start_from in user_list:
            user_list = user_list[user_list.index(start_from):]

        for usr in user_list:
            is_created = False
            if not teamid:
                is_created = self.ghc.add_user_to_organisation(usr)
            else:
                # is_created = self.ghc.add_user_to_team(usr, teamid)
                is_created = GHAPI.invite_user_team(self.cfg.get_api_key(), teamid, usr)

            if not is_created:
                logging.warn('Unable to invite user %s. Stopping.', usr)
                print('Restart script from user:', usr)
                break
            else:
                print(usr)
            time.sleep(2)

    def extract_team_info(self, csv_file):

        user_list=parsers.csvparser.get_rows_as_list(csv_file)[1:]
        users_to_check=list(map(lambda x: [x[-2].lower().strip(), x[-3], x[-4], x[0], x[-1]], user_list))

        team_list=defaultdict(list)
        student_details={}
        for user, team, email, name, team_no in users_to_check :
            # if int(team[2])==6:
            team_list[team+"-"+team_no[-1]].append(user)
            student_details[user]=(email, name)
        return team_list, student_details
