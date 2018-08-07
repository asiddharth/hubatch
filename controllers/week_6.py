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
UI_PNG_SUBSTRINGS = ["ui", ".png"]
DEVELOPER_GUIDE = "DeveloperGuide.adoc"
USER_GUIDE = "UserGuide.adoc"
README = "README.adoc"
ABOUT_US = "AboutUs.adoc"
JAVA = ".java"
FXML = ".fxml"
MESSAGE_TEMPLATE = "controllers/data/message_template.json"
OUTPUT_DIR = "./output/"
CSV_HEADER = ["Student", "Team", "Repo", "Fork", "DG", "UG", "AboutUs", "README", "Java", "RELEASE", "JAR"]
DUMMY = "dummy"
WEEK = 6
SLEEP_TIME = 3

with open(MESSAGE_TEMPLATE, 'r') as f:
    message_template=json.load(f)

class Week_6(BaseController):
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
        parser.add_argument('-audit_csv', type=str,
                            help='filename of the CSV containing audit details for each student')
        parser.add_argument('-d', '--day', type=str,
                            help='which day\'s teams to consider for posting of feedback')
        parser.set_defaults(func=self.create_feedback)


    def audit_week(self, args):
        """
        Calculates student deliverables for the week and saves them to a csv file
        Task-1: Check Team Repo Set Up
        Task-2 Check the forks made by each student
        Task-3 Check commits for DeveloperGuide.adoc, UserGuide.adoc, README.adoc, AboutUs.adoc, java/fxml code
        """
        logging.debug('CSV datafile: %s', args.csv)

        team_repositories, teams_with_repo, team_list=self.check_team_repo_setup(args)
        student_with_forks=self.check_team_forks(team_repositories)
        student_DGs, student_UGs, student_About_Us, \
            student_Readme, student_java_code = self.check_file_changes(team_repositories, team_list, args)
        output_file=self.write_week_to_csv(team_list, teams_with_repo, student_with_forks, student_DGs, \
                                 student_UGs, student_About_Us, student_Readme, student_java_code,args.day)

    def create_feedback(self, args):
        """
        Creates and posts feedback methods for each team and their students
        """
        logging.debug('Reading audit from csv: %s', args.csv)

        audit_details = self.read_audit_details(args)
        teams_to_check=self.extract_team_info(args.csv, args.day)
        teamwise_feedback_messages = self.get_feedback_message(teams_to_check, audit_details)

        self.post_feedback(teamwise_feedback_messages)

    def post_feedback(self, feedbacks):
        """
        Posts feedback to each teams repo
        :param feedback: dictionary of feedbacks[team] = feedback_message
        """

        ghc=GitHubConnector(self.cfg.get_api_key(), self.cfg.get_repo(), self.cfg.get_organisation())

        for team, feedback in feedbacks.items():
            print(team)
            ghc.create_issue(title='Feedback on progress for week {} : Team {}'.format(WEEK, team), msg=feedback, assignee=None)
            time.sleep(SLEEP_TIME)

    def get_feedback_message(self, teams_to_check, audit_details):
        """
        Creates the feedback message for each team
        :param teams_to_check: dictionary(key=teams, value=list of students in the team) of valid teams in that week
        :param audit_details: pandas dataframe of audit_csv
        :return feedback_messages: dictionary of feedbacks[team] = feedback_message
        """

        message = message_template["week{}".format(WEEK)]
        feedback_messages={}

        for team, students in teams_to_check.items():
            
            final_message=""
            # Creating team feedback message
            team_index=audit_details.index[audit_details['Team']==team][0]
            team_message="\n\tCreation of project repository."
            if audit_details["Repo"][team_index]:
                message["team"]=message["team"].format(team, team_message, "\n\tNone")
            else:
                message["team"]=message["team"].format(team, "\n\tNone", team_message)
            final_message+= message["team"]

            #Creating individual feedback messageer
            student_message_Fork = "\n\tCreating personal forks of the team project repositoty."
            student_message_DG = "\n\tUpdating the Developer Guide."
            student_message_UG = "\n\tUpdating the User Guide."
            student_message_AboutUs = "\n\tUpdating the About Us page."
            student_message_README = "\n\tUpdating the README file."
            student_message_Java = "\n\tUpdating Java code."

            for student in students:
                done_message, not_done_message="", ""   
                indiv_index=audit_details.index[audit_details['Student']==student][0]
                
                if audit_details["Fork"][indiv_index]:
                    done_message+=student_message_Fork
                else:
                    not_done_message+=student_message_Fork

                if audit_details["DG"][indiv_index]:
                    done_message+=student_message_DG
                else:
                    not_done_message+=student_message_DG

                if audit_details["UG"][indiv_index]:
                    done_message+=student_message_UG
                else:
                    not_done_message+=student_message_UG

                if audit_details["AboutUs"][indiv_index]:
                    done_message+=student_message_AboutUs
                else:
                    not_done_message+=student_message_AboutUs

                if audit_details["README"][indiv_index]:
                    done_message+=student_message_README
                else:
                    not_done_message+=student_message_README

                if audit_details["Java"][indiv_index]:
                    done_message+=student_message_Java
                else:
                    not_done_message+=student_message_Java

                if len(done_message)==0:
                    done_message="\n\tNone"
                if len(not_done_message)==0:
                    not_done_message="\n\tNone"
                final_message+= message["indiv"].format(DUMMY, done_message, not_done_message)
            
            final_message+=message["tutor"].format(DUMMY)
            feedback_messages[team]=final_message

        return feedback_messages

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
        students_with_forks=[]
        for repo, students in repositories:
            forks_made=[fork.full_name.split("/")[0] for fork in repo.get_forks()]
            students_with_forks+=forks_made
        return students_with_forks



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

    def check_jar_releaseTag_existence(self, teams_to_check, start_datetime, end_datetime):
        teams_with_release, teams_without_release, teams_with_jar, teams_without_jar = {}, {}, {}, {}
        for team, students in teams_to_check.items():
            repository = TEAM_REPO_PREFIX + str(team) + "/main"
            try:
                repository = Github(self.cfg.get_api_key()).get_repo(repository)
                repository_releases = repository.get_releases()
                for release in repository_releases :
                    if release.published_at <= end_datetime and release.published_at >= start_datetime :
                        if release.tag_name is not None :
                            teams_with_release[team] = students
                        if release.tarball_url is not None or release.zipball_url is not None :
                            teams_with_jar[team] = students
                if teams_with_release.get(team, None) is None :
                    teams_without_release[team] = students
                if teams_with_jar.get(team, None) is None :
                    teams_without_jar[team] = students

            except GithubException as e:
                logging.error('Unexpected error Team {}'.format(team))
        return teams_with_release, teams_without_release, teams_with_jar, teams_without_jar

    def write_week_to_csv(self, team_list, teams_with_repo, student_with_forks, student_DGs, \
                            student_UGs, student_About_Us, student_Readme, student_java_code, day) :
        """
        Writes audit details of week in a csv file
        :param team_list: dictionary of all the teams to be considered for corresponding "day"
        :param teams_with_repo: list of all the teams which have created their project repo
        :param student_with_forks: list of all the students who have created personal forks
        :param student_DGs: dictionary[student] = count of DG commits in the provided time
        :param student_UGs: dictionary[student] = count of UG commits in the provided time
        :param student_About_Us: dictionary[student] = count of About_Us file commits in the provided time
        :param student_Readme: dictionary[student] = count of Readme file commits in the provided time
        :param student_java_code: dictionary[student] = count of Java/Fxml files updated by student in provided time
        :param day: day of the week whose teams are considered
        :return output_file: location of the audit output csv file
        """
        output_path = OUTPUT_DIR+"/week_{}/".format(WEEK)
        output_file = output_path+"week_{}_audit_day{}.csv".format(WEEK, day)

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        wr = csv.writer(open(output_file, 'w'), delimiter=',', 
                            quoting=csv.QUOTE_ALL)
        wr.writerow(CSV_HEADER)
        for team, students in team_list.items():
            for student in students:
                to_print=[]
                to_print.append(student)
                to_print.append(team)
                to_print.append(team in teams_with_repo)
                to_print.append(student in student_with_forks)
                to_print.append(student_DGs[student] > 0)
                to_print.append(student_UGs[student] > 0)
                to_print.append(student_About_Us[student] > 0)
                to_print.append(student_Readme[student] > 0)
                to_print .append(student_java_code[student] > 0)
                wr.writerow(to_print)

        return output_file




		