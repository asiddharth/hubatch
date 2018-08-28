"""
Auditing activities for week 6
"""
from .common import BaseController
from connectors.github import GitHubConnector
from github import Github, GithubException

import parsers
import sys
import datetime
import os
import csv
import json
from collections import defaultdict

import logging, time

TEAM_REPO_PREFIX = "CS2103JAN2018-"
DEVELOPER_GUIDE = "DeveloperGuide.adoc"
USER_GUIDE = "UserGuide.adoc"
README = "README.adoc"
ABOUT_US = "AboutUs.adoc"
JAVA = ".java"
FXML = ".fxml"
MESSAGE_TEMPLATE = "controllers/data/message_template.json"
OUTPUT_DIR = "./output/"


class General(BaseController):
    def __init__(self, cfg):
        self.cfg=cfg

    def setup_argparse(self, subparsers):
        """
        Sets up subparsers for general deliverables
        """
        parser=subparsers.add_parser('general', help='GitHub student general auditing tools')
        general_parser=parser.add_subparsers()
        self.setup_general_script_parser(general_parser)

    def setup_general_script_parser(self, subparsers):
        """
        Subparser for auditing student's PRs and submissions
        """
        parser=subparsers.add_parser('scripts', help='scripts to check numerous scripts')
        parser.add_argument('-csv', type=str,
                            help='filename of the CSV containing a list of GitHub users and meta-details')
        parser.add_argument('-s', '--start_date', type=str,
                            help='Start date of the commit submissions')
        parser.add_argument('-e', '--end_date', type=str,
                            help='Deadline of the commit submissions')
        parser.add_argument('-d', '--day', type=str,
                            help='Deadline day of the week')
        parser.set_defaults(func=self.general_script)


    def general_script(self, args):

        team_repositories, teams_with_repo, team_list=self.check_team_repo_setup(args) 
        self.check_forking_workflow(team_list, team_repositories, args)
        
    def check_forking_workflow(self, team_list, team_repositories, args):


        start_datetime=datetime.datetime.strptime(args.start_date, '%d/%m/%Y')
        end_datetime=datetime.datetime.strptime(args.end_date, '%d/%m/%Y')

        for repo, students in team_repositories:
            if "W09-B2" in repo.full_name:
                print(repo.full_name)

                # Get forks of students
                student_forks = self.get_team_forks(repo, students)

                for pull_request in repo.get_pulls(state="all", sort="updated", direction="desc"):
                    if (pull_request.created_at <= end_datetime) and (pull_request.created_at >= start_datetime):
                        if "collated" in pull_request.title:
                            for commits in pull_request.get_commits():
                                print(student_forks[commits.author.login].get_commit(commits.sha).author.login)
                                print(commits.author.login, commits.sha)

    def read_audit_details(self, args):
        """
        Read the audit details stored in csv as pandas dataframe
        """
        user_audit_details = parsers.csvparser.get_pandas_list(args.audit_csv)
        return user_audit_details


    def check_file_changes(self, repositories, team_list, args):
        """
        Counts the number of changes made by student for each required files.
        :param repositories: PyGitHub repository objects of all the team's repositories (teams which have repos created)
        :param team_list: dictionary(key=teams, value=list of students in the team) of valid teams in that week
        :return student_* : dictionary(key=student, value=count of file changed)
        """

        student_DGs,student_UGs={}, {}
        student_About_Us, student_Readme={}, {}
        student_java_code={}
        for team, students in team_list.items():
            for student in students:
                student_DGs[student]=0
                student_UGs[student]=0
                student_About_Us[student]=0
                student_Readme[student]=0
                student_java_code[student]=0


        start_datetime=datetime.datetime.strptime(args.start_date, '%d/%m/%Y')
        end_datetime=datetime.datetime.strptime(args.end_date, '%d/%m/%Y')

        for repo, students in repositories:
            print(repo.full_name)

            for pull_request in repo.get_pulls(state="all", sort="updated", direction="desc"):
                try:
                    if (pull_request.created_at <= end_datetime) and (pull_request.created_at >= start_datetime):  
                        for commit in pull_request.get_commits():
                            login_name = commit.author.login.lower()
                            for file in commit.files:
                                if (DEVELOPER_GUIDE in file.filename) and (login_name is not None):
                                    student_DGs[login_name]+=1
                                elif (USER_GUIDE in file.filename) and (login_name is not None):
                                    student_UGs[login_name]+=1
                                elif (ABOUT_US in file.filename) and (login_name is not None):
                                    student_About_Us[login_name]+=1
                                elif (README in file.filename) and (login_name is not None):
                                    student_Readme[login_name]+=1
                                elif ((JAVA in file.filename) or (FXML in file.filename)) and (login_name is not None):
                                    student_java_code[login_name]+=1
                except:
                    continue

        return student_DGs, student_UGs, student_About_Us, student_Readme, student_java_code

    def check_team_forks(self, repositories):
        """
        Checks which students have created their personal forks
        :param repositories: PyGitHub repository objects of all the team's repositories (teams which have repos created)
        :return students_with_forks: list of students who have created personal forks of team repos
        """
        students_with_forks={}
        for repo, students in repositories:
            forks_made=[fork.full_name.split("/")[0] for fork in repo.get_forks()]
            students_with_forks+=forks_made
        return students_with_forks

    def get_team_forks(self, repo, students):

        forks={}
        for fork in repo.get_forks():
            student = fork.full_name.split("/")[0]
            forks[student] = fork
        return forks





    def check_team_repo_setup(self, args):
        """
        Base function to check the creation of repos by relevant teams
        :return repositories: PyGitHub repository objects of all the team's repositories (teams which have repos created)
        :return teams_with_repo: list of teams who have created repo
        :return teams_to_check: dictionary(key=teams, value=list of students in the team) of valid teams in that week
        """
        if parsers.common.are_files_readable(args.csv):
            teams_to_check=self.extract_team_info(args.csv, args.day)
            teams_with_repo, teams_without_repo, repositories=self.check_repo_existence(teams_to_check)
            return repositories, teams_with_repo, teams_to_check

        else:
            sys.exit(1)

    def extract_team_info(self, csv_file, day):
        """
        Extracts relevant team (and their students) details based on the day of the week
        :param csv_file: location fo the csv_file which contains team information for the course
        :param day: day of the week - teams belonging to this day shall be considered
        :return team_list: dictionary of relevant teams and the students within them
        """
        user_list = parsers.csvparser.get_rows_as_list(csv_file)[1:]
        users_to_check = list(map(lambda x: [x[-1].lower(), x[-2]],
                              filter(lambda x: x[1][0] == day, user_list)))
        team_list = defaultdict(list)
        for user,team in users_to_check :
            team_list[team].append(user)
        return team_list


    def check_repo_existence(self, teams_to_check):
        """
        Checks whether a repo has been created for each team
        :param teams_to_check: dictionary of teams (and their students) whose repo's need to be checked
        :return teams_with_repo: list of teams who have created repo
        :return teams_without_repo: list of teams who haven't created repo
        :return repo_objects: PyGitHub repository objects of all the team's repositories (teams which have repos created)
        """
        teams_with_repo, teams_without_repo={}, {}
        repo_objects = []
        for team, students in teams_to_check.items():
            repository=TEAM_REPO_PREFIX+str(team)+"/main"
            try:
                repository =  Github(self.cfg.get_api_key()).get_repo(repository)
                repository_name = repository.full_name
                repo_objects.append((repository, students))
                teams_with_repo[team]= students

            except GithubException as e:
                logging.error('Team repo for {} not found!'.format(team))
                teams_without_repo[team]=students
        return teams_with_repo, teams_without_repo, repo_objects





    def check_jar_and_releaseTag(self, args) :
        if parsers.common.are_files_readable(args.csv):
            start_datetime = datetime.datetime.strptime(args.start_date, '%d/%m/%Y')
            end_datetime = datetime.datetime.strptime(args.end_date, '%d/%m/%Y')
            teams_to_check = self.extract_team_info(args.csv, args.day)
            teams_with_release, teams_without_release, teams_with_jar, teams_without_jar = \
                self.check_jar_releaseTag_existence(teams_to_check, start_datetime, end_datetime)
            return teams_with_release, teams_without_release, teams_with_jar, teams_without_jar

        else :
            sys.exit(1)

    def check_team_ui_png(self, args):
        teams_to_check = self.extract_team_info(args.csv, args.day)
        team_ui_png = {}
        for team, students in teams_to_check.items():
            team_ui_png[team] = 0

        start_datetime=datetime.datetime.strptime(args.start_date, '%d/%m/%Y')
        end_datetime=datetime.datetime.strptime(args.end_date, '%d/%m/%Y')

        for team, students in teams_to_check.items():
            organization = TEAM_REPO_PREFIX + str(team)
            repo =  GitHubConnector(self.cfg.get_api_key(),organization+ "/main", organization).repo
            found = False
            for pull_request in repo.get_pulls(state="all", sort="updated", direction="desc"):
                try:
                    if (pull_request.created_at <= end_datetime) and (pull_request.created_at >= start_datetime) \
                            and found == False:
                        for commit in pull_request.get_commits():
                            for file in commit.files:
                                is_image_file = True
                                for checkstring in UI_PNG_SUBSTRINGS :
                                    is_image_file = True
                                    if checkstring not in file.filename.lower() :
                                        is_image_file = False
                                        break
                                if is_image_file == True :
                                    team_ui_png[team] = 1
                                    found = True
                                    break
                except:
                    continue
        return team_ui_png






		