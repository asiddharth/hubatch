"""
Auditing activities for week 3
"""
from .common import BaseController
from connectors.github import GitHubConnector
from github import Github, GithubException

import parsers
import smtplib
import sys
import datetime
from datetime import timedelta
import os
import csv
import json
from collections import defaultdict
import logging, time

#############################################################
COURSE = "CS2113"
GMAIL_USER = 'cs2113.bot@gmail.com'  
GMAIL_PASSWORD = 'cs2113.bot.feedback'
TEST_EMAIL = "hdevamanyu@student.nitw.ac.in"

ADDRESSBOOK_REPO = "nusCS2113-AY1819S1/addressbook-level1"

PRODUCTION = False
##############################################################

COMMITS_TO_IGNORE = ["ca2ab8c7cbf6b303f6e93327fbbdcc8250714067", "a9270ee306badf96936da1ba6dbf98f95cc49ed7", \
                     "48d94378331364a0a0fa3748817bcaae15f33893", "13daa30527fb541e6e7d073ec308537d1f21d871", \
                     "1827da83a97e94fd7cd2c663f3c2a2b6f114250e"]
COURSE_EMAIL = COURSE.lower()+"@comp.nus.edu.sg"
DEVELOPER_GUIDE = "DeveloperGuide.adoc"
USER_GUIDE = "UserGuide.adoc"
README = "README.adoc"
ABOUT_US = "AboutUs.adoc"
JAVA = ".java"
FXML = ".fxml"
TEST = "test/"
MESSAGE_TEMPLATE = "controllers/data/message_template.json"
CSV_HEADER = ["Student", "Team", "Fork", "Java", "Test", "UG"]
OUTPUT_DIR = "./output/"
DUMMY = "dummy"
WEEK = 3
SLEEP_TIME = 3

with open(MESSAGE_TEMPLATE, 'r') as f:
    message_template=json.load(f)

class Week_3(BaseController):
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
        parser.add_argument('-e', '--end_date', type=str,
                            help='Deadline of the commit submissions')
        parser.add_argument('-d', '--day', type=str,
                            help='which day\'s teams to consider for posting of feedback')
        parser.set_defaults(func=self.create_feedback)

    def create_feedback(self, args):
        """
        Creates and emails feedback methods for each student
        """
        logging.debug('Reading audit from csv: %s', args.csv)

        audit_details = self.read_audit_details(args)
        teams_to_check, student_details=self.extract_team_info(args.csv, args.day)
        student_forks_addressbook=self.get_student_forks(teams_to_check, args)
        student_feedback_messages = self.get_feedback_message(teams_to_check, student_details, audit_details, student_forks_addressbook, args)
        self.mail_feedback(student_feedback_messages, student_details)

    def mail_feedback(self, student_feedback_messages, student_details):

        if PRODUCTION:
            response = input("\n\nALERT!!\n\nAre you sure to send actual emails? [Y/n]")
            response = response.lower()
            if "n" in response:
                exit()

        server_ssl = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server_ssl.ehlo()
        server_ssl.login(GMAIL_USER, GMAIL_PASSWORD)

        mail_subject=message_template["week{}".format(WEEK)]["mail_subject"]

        for student, message in student_feedback_messages.items():
            mail_message = 'Subject: {}\n\n{}'.format(mail_subject.format(COURSE, WEEK), message)
            
            print(student, student_details[student][0])
            print(mail_message)
            
            dest_email = student_details[student][0] if PRODUCTION else TEST_EMAIL

            mail = server_ssl.sendmail(GMAIL_USER, dest_email, mail_message)
            time.sleep(SLEEP_TIME)
        server_ssl.close()


    def get_feedback_message(self, teams_to_check,  student_details, audit_details, student_forks, args): 
        """
        Creates the feedback message for each team
        :param teams_to_check: dictionary(key=teams, value=list of students in the team) of valid teams in that week
        :param audit_details: pandas dataframe of audit_csv
        :return feedback_messages: dictionary of feedbacks[team] = feedback_message
        """

        message = message_template["week{}".format(WEEK)]
        feedback_messages={}

        for team, students in teams_to_check.items():
            for student in students:
                if student == "":
                    continue
                try:
                    index = audit_details.index[audit_details['Student']==student][0]
                except:
                    continue
                final_message=""
                if audit_details["Fork"][index] == 1:
                    final_message=message["indiv_fork"]
                    local_message=""
                    if audit_details["Test"][index] >= 1:
                        local_message+=message["test"]
                    if audit_details["UG"][index] >= 1:
                        local_message+=message["docs"]
                    if len(local_message)>1:
                        local_message="\n\n Kudos for doing these too:"+local_message
                    final_message = final_message.format(student_details[student][1], student_forks[student].full_name, \
                                                         args.end_date, local_message, COURSE, args.end_date, COURSE)
                
                    if audit_details["Java"][index] ==0:
                        final_message =""

                if final_message=="":
                    final_message=message["indiv_no_fork"]
                    final_message=final_message.format(student_details[student][1], student+"/addressbook-level1", COURSE, args.end_date, COURSE)

                feedback_messages[student]=final_message

        return feedback_messages

    def read_audit_details(self, args):
        """
        Read the audit details stored in csv as pandas dataframe
        """
        user_audit_details = parsers.csvparser.get_pandas_list(args.audit_csv)
        return user_audit_details



    def audit_week(self, args):
        """
        Calculates student deliverables for the week and saves them to a csv file
        Task-1: Check Team Repo Set Up
        Task-2 Check the forks made by each student
        Task-3 Check commits for DeveloperGuide.adoc, UserGuide.adoc, README.adoc, AboutUs.adoc, java/fxml code
        """
        logging.debug('CSV datafile: %s', args.csv)
        if parsers.common.are_files_readable(args.csv):
            teams_to_check, student_details=self.extract_team_info(args.csv, args.day)
        student_forks_addressbook=self.get_student_forks(teams_to_check, args)
        code_change, test_change, student_UG=self.check_file_changes(teams_to_check, student_forks_addressbook, args)
        output_file=self.write_week_to_csv(teams_to_check, list(student_forks_addressbook.keys()), code_change, \
                                           test_change, student_UG, args.day)


    def check_file_changes(self, team_list, forks, args):

        code_change, test_change={}, {}
        student_UG={}
        for team, students in team_list.items():
            for student in students:
                code_change[student]=0
                test_change[student]=0
                student_UG[student]=0

        start_datetime=datetime.datetime.strptime(args.start_date, '%d/%m/%Y')
        end_datetime=datetime.datetime.strptime(args.end_date, '%d/%m/%Y')+timedelta(days=1)

        for student, fork in forks.items():

            branches=[]
            for branch in fork.get_branches():
                branches.append(branch.name)

            print(fork.full_name)
            for branch in branches:
                for commit in fork.get_commits(sha=branch, since=start_datetime, until=end_datetime):
                    try:
                        # login_name = commit.author.login.lower()
                        login_name = student
                        commit_sha = commit.sha
                        # if login_name == student:
                        if commit_sha not in COMMITS_TO_IGNORE:
                            for file in commit.files:
                                if ((JAVA in file.filename) or (FXML in file.filename)) and (login_name is not None):
                                    code_change[login_name]+=1
                                elif (TEST in file.filename) and (login_name is not None):
                                    test_change[login_name]+=1
                                elif (USER_GUIDE in file.filename) and (login_name is not None):
                                    student_UG[login_name]+=1
                    except:
                        continue
        return code_change, test_change, student_UG



    def extract_team_info(self, csv_file, day):

        user_list=parsers.csvparser.get_rows_as_list(csv_file)[1:]
        users_to_check=list(map(lambda x: [x[-2].lower().strip(), x[-3], x[-4], x[0]],
                              filter(lambda x: x[3][0] == day, user_list)))
        team_list=defaultdict(list)
        student_details={}
        for user, team, email, name in users_to_check :
            team_list[team].append(user)
            student_details[user]=(email, name)
        return team_list, student_details


    def get_student_forks(self, team_list, args):

        student_list=[]
        for team, students in team_list.items():
            student_list+=students

        addressbook=Github(self.cfg.get_api_key()).get_repo(ADDRESSBOOK_REPO)
        student_forks={}
        for fork in addressbook.get_forks():
            student_name=fork.full_name.split("/")[0].lower()
            if student_name in student_list:
                student_forks[student_name]=fork

        return student_forks

    def write_week_to_csv(self, team_list, fork_list, code_changes, test_changes, ug_changes, day) :

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
                to_print.append(int(student in fork_list))
                to_print.append(int(code_changes[student]))
                to_print.append(int(test_changes[student]))
                to_print.append(int(ug_changes[student]))

                if student != "":
                    wr.writerow(to_print)

        return output_file