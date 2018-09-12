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
import re
from collections import defaultdict
import logging, time
import numpy as np

#############################################################
COURSE = "CS2113"
GMAIL_USER = 'cs2113.bot@gmail.com'  
GMAIL_PASSWORD = 'cs2113.bot.feedback'
TEST_EMAIL = "hdevamanyu@student.nitw.ac.in"

ADDRESSBOOK_REPO = "nusCS2113-AY1819S1/addressbook-level2"
QUESTION_TO_CHECK = "[w5.11]"
PRODUCTION = False
##############################################################

COURSE_EMAIL = COURSE.lower()+"@comp.nus.edu.sg"
DEVELOPER_GUIDE = "DeveloperGuide.adoc"
USER_GUIDE = "UserGuide.adoc"
README = "README.adoc"
ABOUT_US = "AboutUs.adoc"
JAVA = ".java"
FXML = ".fxml"
TEST = "test/"
MESSAGE_TEMPLATE = "controllers/data/message_template.json"
CSV_HEADER = ["Student", "Team", "Java", "UG", "DG", "Test", "Junit", "Peer_Review"]
OUTPUT_DIR = "./output/"
DUMMY = "dummy"
WEEK = 5
SLEEP_TIME = 3

with open(MESSAGE_TEMPLATE, 'r') as f:
    message_template=json.load(f)

class Week_5(BaseController):
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
        student_feedback_messages = self.get_feedback_message(teams_to_check, student_details, audit_details, args)
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

    def get_feedback_message(self, teams_to_check,  student_details, audit_details, args): 

        message = message_template["week{}".format(WEEK)]
        feedback_messages={}
        

        for team, students in teams_to_check.items():
            for student in students:
                if student == "":
                    continue
                try:
                    index = audit_details.index[audit_details['Student']==student][0]
                except:
                    print("Here")
                    continue

                final_message=""
                if np.sum(np.asarray(audit_details.iloc[index])[2:7]) >= 1:
                    code_mark= 1 if (audit_details["Java"][index] >=1) else 0
                    test_or_doc_mark=0
                    if (audit_details["UG"][index] >=1) or (audit_details["DG"][index] >=1) or (audit_details["Test"][index] >=1):
                        test_or_doc_mark=1
                    total_marks = code_mark+test_or_doc_mark
                    kudos_message=""
                    if (audit_details["Junit"][index]>=1):
                        kudos_message="\n\n Kudos for implementing JUnit tests!"
                    peer_review_message = message["bonus"] if (audit_details["Peer_Review"][index]>=1) else message["no_bonus"]

                    final_message = message["indiv_PR"].format(student_details[student][1], args.end_date, str(total_marks),\
                                                               str(code_mark), str(test_or_doc_mark), kudos_message, peer_review_message, \
                                                               COURSE, args.end_date, COURSE)

                else:
                    peer_review_message = message["bonus"] if (audit_details["Peer_Review"][index]>=1) else message["no_bonus"]
                    final_message = message["indiv_no_PR"].format(student_details[student][1], args.end_date,peer_review_message, \
                                                                  COURSE, args.end_date, COURSE)
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

        # student_forks_addressbook=self.get_student_forks(teams_to_check, args)
        JAVA_student, UG_student, DG_student, Test_student, Junit_student, \
                    peer_review_students=self.check_file_changes(teams_to_check, args)
        output_file=self.write_week_to_csv(teams_to_check, JAVA_student, UG_student, DG_student, \
                                            Test_student, Junit_student, peer_review_students, args.day)

    def is_invalid_pr(self, labels):
        for label in labels:
            if label.name=="FormatCheckRequested":
                return True
        if len(labels)==0:
            return True
        return False

    def check_file_changes(self, teams_to_check, args):

        start_datetime=datetime.datetime.strptime(args.start_date, '%d/%m/%Y')
        end_datetime=datetime.datetime.strptime(args.end_date, '%d/%m/%Y')+timedelta(days=1)

        addressbook=Github(self.cfg.get_api_key()).get_repo(ADDRESSBOOK_REPO)

        peer_review_students=[]

        Junit_student, JAVA_student, UG_student, DG_student, Test_student= {},{},{},{},{}
        for team, students in teams_to_check.items():
            for student in students:
                Junit_student[student]=0
                JAVA_student[student]=0
                UG_student[student]=0
                DG_student[student]=0
                Test_student[student]=0

        for pull_request in addressbook.get_pulls(state="all", sort="updated", direction="desc"):
            if (pull_request.created_at <= end_datetime) and (pull_request.created_at >= start_datetime):


                if self.is_invalid_pr(pull_request.labels):
                    continue

                # if pull_request.title == "[W5.11][W12-1]Elston Aw":
                #     print(pull_request.title)

                #     print("\n Get comments:")
                #     for comment in (pull_request.get_comments()+pull_request.get_issue_comments()+pull_request.get_review_comments()):
                #         print(comment.user.login)

                #     print("\n Get Reviews:")
                #     for comment in pull_request.get_reviews():
                #         print(comment.user.login,comment.state)
                #     print(pull_request.state)
                #     exit()

                # Acquiring info for peer reviews
                for comment in pull_request.get_issue_comments():
                    if (pull_request.user.login != comment.user.login): 
                        peer_review_students.append(comment.user.login.lower())
                for comment in pull_request.get_comments():
                    if (pull_request.user.login != comment.user.login):
                        peer_review_students.append(comment.user.login.lower())
                for comment in pull_request.get_review_comments():
                    if (pull_request.user.login != comment.user.login):
                        peer_review_students.append(comment.user.login.lower())
                for comment in pull_request.get_reviews():
                    if (pull_request.user.login != comment.user.login):
                        peer_review_students.append(comment.user.login.lower())


                try:
                    title_prefix = re.search('\[(W|w).*?\..*?\]', pull_request.title).group()
                    if title_prefix.lower() == QUESTION_TO_CHECK:

                        commiter = pull_request.user.login.lower()
                        print(commiter)
                        for file in pull_request.get_files():
                            filename = file.filename
                            if int(file.changes)>0:
                                if (JAVA in filename) or (FXML in filename):
                                    JAVA_student[commiter]+=1
                                if (USER_GUIDE in filename):
                                    UG_student[commiter]+=1
                                if (DEVELOPER_GUIDE in filename):
                                    DG_student[commiter]+=1
                                if (TEST in filename):
                                    Test_student[commiter]+=1
                                if (TEST in filename) and (JAVA in filename):
                                    Junit_student[commiter]+=1

                        # for commit in pull_request.get_commits():
                        #     try:
                        #         commiter=commit.author.login.lower()
                        #     except:
                        #         commiter=commit.commit.author.name.lower()

                        #     if commit.commit.author.date >= start_datetime:
                        #         for file in commit.files:
                        #             filename=file.filename
                        #             if (JAVA in filename) or (FXML in filename):
                        #                 JAVA_student[commiter]+=1
                        #             if (USER_GUIDE in filename):
                        #                 UG_student[commiter]+=1
                        #             if (DEVELOPER_GUIDE in filename):
                        #                 DG_student[commiter]+=1
                        #             if (TEST in filename):
                        #                 Test_student[commiter]+=1
                        #             if (TEST in filename) and (JAVA in filename):
                        #                 Junit_student[commiter]+=1

                except:
                    continue

        return JAVA_student, UG_student, DG_student, Test_student, Junit_student, peer_review_students

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

    def write_week_to_csv(self, teams_to_check, JAVA_student, UG_student, DG_student, Test_student, Junit_student, peer_review_students, day) :

        output_path = OUTPUT_DIR+"/week_{}/".format(WEEK)
        output_file = output_path+"week_{}_audit_day{}.csv".format(WEEK, day)

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        wr = csv.writer(open(output_file, 'w'), delimiter=',', 
                            quoting=csv.QUOTE_ALL)
        wr.writerow(CSV_HEADER)
        for team, students in teams_to_check.items():
            for student in students:
                to_print=[]
                to_print.append(student)
                to_print.append(team)
                to_print.append(int(JAVA_student[student]))
                to_print.append(int(UG_student[student]))
                to_print.append(int(DG_student[student]))
                to_print.append(int(Test_student[student]))
                to_print.append(int(Junit_student[student]))
                to_print.append(int(student in peer_review_students))
                if student != "":
                    wr.writerow(to_print)

        return output_file
