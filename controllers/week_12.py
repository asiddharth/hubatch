"""
Auditing activities for week 12
"""
from .common import BaseController
from connectors.github import GitHubConnector
from github import Github, GithubException

import parsers
import sys
import smtplib
import datetime
from datetime import timedelta
import os
import csv
import re
import json
import math
import ast
from collections import defaultdict
import socket
import base64
import codecs
from dateutil import parser
from urllib.request import urlopen, URLError, HTTPError
from travispy import TravisPy

import logging, time

#############################################################
COURSE = "CS2103"
TEAM_REPO_PREFIX = "CS2103-AY1819S1-"
GMAIL_USER = 'cs2103.bot@gmail.com'
GMAIL_PASSWORD = 'cs2103.bot.feedback'
MODULE_EMAIL = "cs2103@comp.nus.edu.sg"


TEST_EMAIL = "siddarth15@cse.iitb.ac.in"

ADDRESSBOOK_REPO = ["nus-cs2103-AY1819S1/addressbook-level4"]
AB4="https://github.com/nus-cs2103-AY1819S1/addressbook-level4"
LINK1 = "https://github.com/{}{}/main"
LINK2 = "https://nus-cs2103-ay1819s1.github.io/cs2103-website/admin/project-w12-mid-v14.html"
PPP_LINK = "https://cs2103-ay1819s1-{}.github.io/main/team/{}.html"
REPOSENSE_LINK = "https://nus-cs2103-ay1819s1.github.io/cs2103-dashboard/#=undefined&search="
TIMEDELTA = timedelta(days=1, hours=0) # 2-am checking # Set  timedelta(days=1) for CS2103
TIMEDELTA_MILESTONE = timedelta(hours=1) # next day checking # Set timedelta(days=7) for CS2103
PRODUCTION = False
##############################################################


MILESTONES = ['v1.4', 'v1.3', 'v1.2'] # First item should be the next upcoming 
TAG="v1.4"
PNG=".png"
JPG=".jpg"
JPEG="jpeg"
JAR = ".jar"
UI_PNG_SUBSTRINGS = ["ui", ".png"]
MESSAGE_TEMPLATE = "controllers/data/message_template.json"
OUTPUT_DIR = "./output/"
CSV_HEADER = ["Student", "Team", "Team_Repo", \
              "v1.3_closed", "issue_closed_v1.3", "issue_and milestone_closed_v1.3[0/1]", "UI_PNG",\
              "v1.4_deadline", "v1.4_deadline[0/1]", "issue_allocated_v1.4", \
              "{}_issue_assigned".format(MILESTONES[0]), "PPP_link", "Reposense_linked"]
DUMMY = "dummy"
WEEK = 12
SLEEP_TIME = 3

with open(MESSAGE_TEMPLATE, 'r') as f:
    message_template=json.load(f)

class Week_12(BaseController):
    def __init__(self, cfg):
        self.cfg=cfg

    def setup_argparse(self, subparsers):
        """
        Sets up subparsers for week deliverables
        """
        parser=subparsers.add_parser('week-{}'.format(WEEK), help='GitHub student auditing tools for the week')
        week_parser=parser.add_subparsers()
        self.setup_audit_week_parser(week_parser)
        self.setup_post_week_audit(week_parser)

    def setup_audit_week_parser(self, subparsers):
        """
        Subparser for auditing student's PRs and submissions
        """
        parser=subparsers.add_parser('audit-week', help='perform all submission checks for the week')
        parser.add_argument('-csv', type=str,
                            help='filename of the CSV containing a list of GitHub users and meta-details')
        parser.add_argument('-s', '--start_date', type=str,
                            help='Start date of the commit submissions')
        parser.add_argument('-e', '--end_date', type=str,
                            help='Deadline of the commit submissions')
        parser.add_argument('-d', '--day', type=str,
                            help='Deadline day of the week')
        parser.set_defaults(func=self.audit_week)


    def setup_post_week_audit(self, subparsers):
        """
        Subparser for positng feedback for each team
        """
        parser=subparsers.add_parser('post-feedback', help='create feedback messages for each team')
        parser.add_argument('-csv', type=str,
                            help='filename of the CSV containing a list of GitHub users and meta-details')
        parser.add_argument('-tutor_map', type=str,
                            help='filename of the CSV containing team tutor mapping')
        parser.add_argument('-audit_csv', type=str,
                            help='filename of the CSV containing audit details for each student')
        parser.add_argument('-e', '--end_date', type=str,
                            help='Deadline of the commit submissions')
        parser.add_argument('-d', '--day', type=str,
                            help='which day\'s teams to consider for posting of feedback')
        parser.set_defaults(func=self.create_feedback)



    def create_feedback(self, args):
        """
        Creates and posts feedback methods for each team and their students
        """

        pass

    def read_audit_details(self, path):
        """
        Read the audit details stored in csv as pandas dataframe
        """
        user_audit_details = parsers.csvparser.get_pandas_list(path)
        return user_audit_details













    def audit_week(self, args):

        logging.debug('CSV datafile: %s', args.csv)

        start_datetime=datetime.datetime.strptime(args.start_date, '%d/%m/%Y')
        self.end_datetime=end_datetime=datetime.datetime.strptime(args.end_date, '%d/%m/%Y')+TIMEDELTA


        # Load last weeks output
        LAST_WEEK_AUDIT_PATH = "./output/week_{}/week_{}_audit_day{}.csv".format(str(WEEK-1), str(WEEK-1), args.day.upper())
        self.audit_details_last = self.read_audit_details(LAST_WEEK_AUDIT_PATH)

        team_repositories, teams_with_repo, team_list=self.check_team_repo_setup(args)
        # self.dump_gradle(team_list, args)
        self.check_PPP(team_list)
        self.check_team_level_things(team_list, start_datetime, end_datetime)
        self.check_file_changes(team_repositories, team_list, args, start_datetime, end_datetime)
        
        output_file=self.write_week_to_csv(team_list, teams_with_repo, args.day)

    def dump_gradle(self, team_list, args):

        self.team_dependencies = {}

        for team, student in team_list.items():
            repository = self.team_repo_mapping[team]

            for content in repository.get_dir_contents(path="."):
                if content.name == "build.gradle":
                    decoded_content = str(content.decoded_content)
                    dependencies = re.search('dependencies.*shadowJar', decoded_content).group()
                    self.team_dependencies[team] = codecs.decode(dependencies, 'unicode_escape').rsplit("\n",1)[0].strip()

        self.write_gradle_to_csv(team_list, args.day)

    def check_PPP(self, team_list):

        self.PPP_student=defaultdict(lambda: 0)
        self.reposense_student=defaultdict(lambda: 0)

        for team, students in team_list.items():
            for student in students:
                ppp_link = PPP_LINK.format(team.lower(), student.lower())
                socket.setdefaulttimeout( 23 )  # timeout in seconds
                url = ppp_link
                try :
                    response = urlopen( url )
                except HTTPError as e:
                    print('student: '+student+', the server couldn\'t fulfill the request. Reason:', str(e.code))
                except URLError as e:
                    print('student: '+student+ 'We failed to reach a server. Reason:', str(e.reason))
                else :
                    html = response.read()

                    if REPOSENSE_LINK in str(html):
                        self.reposense_student[student]=1
                    self.PPP_student[student]=1


    def check_file_changes(self, repositories, team_list, args, start_datetime, end_datetime):
        """
        Counts the number of changes made by student for each required files.
        :param repositories: PyGitHub repository objects of all the team's repositories (teams which have repos created)
        :param team_list: dictionary(key=teams, value=list of students in the team) of valid teams in that week
        :return student_* : dictionary(key=student, value=count of file changed)
        """

        self.ui_team=defaultdict(lambda: 0)


        print("Checking pull requests")
        for team, students in team_list.items():
            print(team)
            repo = self.team_repo_mapping[team]
            try:
                repo.full_name
            except:
                continue

            # for pull_request in repo.get_pulls(state="all", sort="updated", direction="desc"):
            #     try:
            #         pull_request_login = pull_request.user.login.lower()
            #         # print(pull_request_login)

            #         if ((pull_request.created_at<=end_datetime) and (pull_request.created_at>=start_datetime)) or \
            #                 ((pull_request.updated_at<=end_datetime) and (pull_request.updated_at>=start_datetime)):


            #             for file in pull_request.get_files():
            #                 filename = file.filename.lower()

            #                 if (UI_PNG_SUBSTRINGS[0] in filename.lower()) and (UI_PNG_SUBSTRINGS[1] in filename.lower()):
            #                     self.ui_team[team]=1

            #     except:
            #         continue

            for commit in repo.get_commits(path="docs/images/", since=start_datetime, until=end_datetime):
                for file in commit.files:
                    if ((UI_PNG_SUBSTRINGS[0]+".") in file.filename.lower()) and (UI_PNG_SUBSTRINGS[1] in file.filename.lower()):
                        self.ui_team[team]=1



    def check_team_repo_setup(self, args):

        if parsers.common.are_files_readable(args.csv):
            teams_to_check, student_details=self.extract_team_info(args.csv, args.day)
            teams_with_repo, repositories=self.check_repo_existence(teams_to_check)
            return repositories, teams_with_repo, teams_to_check

        else:
            sys.exit(1)

    def extract_team_info(self, csv_file, day):

        user_list=parsers.csvparser.get_rows_as_list(csv_file)[1:]
        users_to_check=list(map(lambda x: [x[-2].lower().strip(), x[-3], x[-4], x[0], x[-1]],
                              filter(lambda x: x[3][0] == day, user_list)))

        team_list=defaultdict(list)
        student_details={}
        for user, team, email, name, team_no in users_to_check :
            team_list[team+"-"+team_no[-1]].append(user)
            student_details[user]=(email, name)
        return team_list, student_details


    def check_repo_existence(self, teams_to_check):
        
        teams_with_repo={}
        repo_objects = []
        self.team_repo_mapping={}
        for team, students in teams_to_check.items():
            repository=TEAM_REPO_PREFIX+str(team)+"/main"
            try:
                repository =  Github(self.cfg.get_api_key()).get_repo(repository)
                repository_name = repository.full_name
                repo_objects.append((repository, students))

                teams_with_repo[team]= students
                self.team_repo_mapping[team]=repository

            except GithubException as e:
                logging.error('Team repo for {} not found!'.format(team))
        return teams_with_repo, repo_objects


    def check_team_level_things(self, teams_to_check, start_datetime, end_datetime):

        self.team_milestone_due_date, self.team_milestone_closed_1_3=defaultdict(lambda: ""), defaultdict(lambda: 0)
        self.team_issue_assigned_to_milestone=defaultdict(lambda: "")
        self.team_issues_closed_1_3=defaultdict(lambda: 1)
        self.team_issue_assigned_to_next_milestone=defaultdict(lambda: "")
        self.student_issue_assigned_to_milestone=defaultdict(lambda: 0)



        for team, students in teams_to_check.items():
            if team in self.team_repo_mapping.keys():
                repository = self.team_repo_mapping[team]

                
                repository_labels = repository.get_labels()
                repository_milestones = repository.get_milestones(state='all')

                # Note milestones for the repository
                local_due_date={}
                local_milestone_status={}
                for milestone in repository_milestones:
                    local_due_date[milestone.title.lower()]=milestone.due_on
                    local_milestone_status[milestone.title.lower()]=milestone.state


                for issue in repository.get_issues(state="all"):

                    # check issue assigned current milestone
                    if (issue.milestone is not None) and (MILESTONES[0] in issue.milestone.title.lower()):
                        self.team_issue_assigned_to_milestone[team] = issue.html_url

                        #For such issue, save the assignee
                        for assignee in issue.assignees:
                            self.student_issue_assigned_to_milestone[assignee.login.lower()]+=1

                    # for 1.3
                    if (issue.milestone is not None) and (MILESTONES[1] in issue.milestone.title.lower()):
                        # if any one issue assigned to current milestone is open, then all issues are not closed/merged
                        if issue.state.lower() == "open":   
                            self.team_issues_closed_1_3[team] = 0


                # Current milestone specific
                for milestone, due_date in local_due_date.items():
                    if MILESTONES[0] in milestone.lower():
                        self.team_milestone_due_date[team]=due_date


                for milestone, state in local_milestone_status.items():
                    if (MILESTONES[1] in milestone.lower()) and (state != "open"):
                        self.team_milestone_closed_1_3[team]=1



    def write_week_to_csv(self, team_list, teams_with_repo,  day):

        output_path = OUTPUT_DIR+"/week_{}/".format(WEEK)
        output_file = output_path+"week_{}_audit_day{}.csv".format(WEEK, day)

        if not os.path.exists(output_path):
            os.makedirs(output_path)
        wr = csv.writer(open(output_file, 'w'), delimiter=',', quoting=csv.QUOTE_ALL)
        wr.writerow(CSV_HEADER)

        
        print("Printing")

        for team, students in team_list.items():
            print(team)
            for student in students:
                to_print=[]
                to_print.append(student)
                to_print.append(team)
                to_print.append(int(team in teams_with_repo))
                to_print.append(int(self.team_milestone_closed_1_3[team]>0))
                to_print.append(int(self.team_issues_closed_1_3[team]>0))
                to_print.append(int(bool(self.team_milestone_closed_1_3[team]) and bool(self.team_issues_closed_1_3[team])))
                to_print.append(int(self.ui_team[team] > 0))
                to_print.append(self.team_milestone_due_date[team])

                try:
                    if (self.team_milestone_due_date[team] <= (self.end_datetime+TIMEDELTA_MILESTONE)):
                        to_print.append(1)
                    else:
                        exit()
                except:
                    to_print.append(0)


                to_print.append(self.team_issue_assigned_to_milestone[team])

                to_print.append(int(self.student_issue_assigned_to_milestone[student] > 0))
                to_print.append(int(self.PPP_student[student] > 0))
                to_print.append(int(self.reposense_student[student] > 0))
                wr.writerow(to_print)

        return output_file

    def write_gradle_to_csv(self, team_list, day):

        output_path = OUTPUT_DIR+"/week_{}/".format(WEEK)
        output_file = output_path+"week_{}_gradle_{}.csv".format(WEEK, day)

        if not os.path.exists(output_path):
            os.makedirs(output_path)
        wr = csv.writer(open(output_file, 'w'), delimiter=',', quoting=csv.QUOTE_ALL)


        for team, students in team_list.items():
            to_print=[]
            to_print.append(team)
            to_print.append(self.team_dependencies[team])
            wr.writerow(to_print)