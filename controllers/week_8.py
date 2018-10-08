"""
Auditing activities for week 6
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
from collections import defaultdict
import socket
from urllib.request import urlopen, URLError, HTTPError

import logging, time

#############################################################
COURSE = "CS2113"
TEAM_REPO_PREFIX = "CS2113-AY1819S1-"
GMAIL_USER = 'cs2113.bot@gmail.com'  
GMAIL_PASSWORD = 'cs2113.bot.feedback'
MODULE_EMAIL = "cs2113@comp.nus.edu.sg"


TEST_EMAIL = "hdevamanyu@student.nitw.ac.in"

ADDRESSBOOK_REPO = ["nusCS2113-AY1819S1/addressbook-level4", "nusCS2113-AY1819S1/addressbook-level3"]
AB3="https://github.com/nusCS2113-AY1819S1/addressbook-level3"
AB4="https://github.com/nusCS2113-AY1819S1/addressbook-level4"
LINK1 = "https://github.com/{}{}/main"
LINK2 = "https://nuscs2113-ay1819s1.github.io/website/admin/project-w07-v11.html"
PRODUCTION = False
##############################################################

TYPE = "type."
PRIORITY = "priority."
MILESTONES = ['v1.2', 'v1.3', 'v1.4']
TAG="v1.2"
PNG=".png"
JPG=".jpg"
JPEG="jpeg"
UI_PNG_SUBSTRINGS = ["ui", ".png"]
DEVELOPER_GUIDE = "DeveloperGuide.adoc"
USER_GUIDE = "UserGuide.adoc"
README = "README.adoc"
ABOUT_US = "AboutUs.adoc"
JAVA = ".java"
FXML = ".fxml"
MESSAGE_TEMPLATE = "controllers/data/message_template.json"
OUTPUT_DIR = "./output/"
CSV_HEADER = ["Student", "Team", "Team_Repo", "Team_PR", "Auto_Publish", "UI_PNG", "Git tag", "Fork", "DG", "UG", "AboutUs", "README", "Java", "Peer_Review", "Photo"]
DUMMY = "dummy"
WEEK = 8
SLEEP_TIME = 3

with open(MESSAGE_TEMPLATE, 'r') as f:
    message_template=json.load(f)

class Week_8(BaseController):
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


    def audit_week(self, args):

        logging.debug('CSV datafile: %s', args.csv)

        start_datetime=datetime.datetime.strptime(args.start_date, '%d/%m/%Y')
        end_datetime=datetime.datetime.strptime(args.end_date, '%d/%m/%Y')+timedelta(days=1, hours=2) # 2-am checking


        team_repositories, teams_with_repo, team_list=self.check_team_repo_setup(args)
        teams_with_tag=self.check_jar_releaseTag_existence(team_list, start_datetime, end_datetime)
        teams_with_PR=self.check_if_PR_sent(team_list, args, start_datetime, end_datetime)
        autopublished_teams=self.check_autopublishing(team_list, args)
        student_with_forks=self.check_team_forks(team_repositories)
        student_DGs, student_UGs, student_About_Us, \
            student_Readme, student_java_code, ui_team, \
            student_photo, peer_review_students = self.check_file_changes(team_repositories, team_list, args, start_datetime, end_datetime)

        output_file=self.write_week_to_csv(team_list, teams_with_repo, teams_with_PR, student_with_forks, student_DGs, \
                                 student_UGs, student_About_Us, student_Readme, student_java_code, ui_team, \
                                 student_photo, peer_review_students, autopublished_teams, teams_with_tag, args.day)

    def create_feedback(self, args):
        """
        Creates and posts feedback methods for each team and their students
        """

        end_datetime=datetime.datetime.strptime(args.end_date, '%d/%m/%Y')+timedelta(days=1, hours=2) # 2-am checking


        logging.debug('Reading audit from csv: %s', args.csv)
        audit_details = self.read_audit_details(args)
        teams_to_check, student_details=self.extract_team_info(args.csv, args.day)
        tutor_map=self.load_tutor_map(args.tutor_map)
        feedback_messages, no_team_repo, no_issue_tracker, no_team_repo_list = self.get_feedback_message(teams_to_check, tutor_map, audit_details, args, end_datetime)
        self.post_feedback(teams_to_check, feedback_messages, no_team_repo, no_team_repo_list, no_issue_tracker, student_details, tutor_map )


    def post_feedback(self, teams_to_check, feedbacks, no_team_repo, no_team_repo_list, no_issue_tracker, student_details, tutor_map):
        """
        Posts feedback to each teams repo
        :param feedback: dictionary of feedbacks[team] = feedback_message
        """

        for team, feedback in feedbacks.items():

            if team in no_team_repo_list:
                TA = tutor_map[team][1]
                mail_message=no_team_repo[team]
                student_mails=[]
                for student in teams_to_check[team]:
                    student_mails.append(student_details[student][0])
                self.mail_feedback(mail_message, student_mails, TA)
            else:
                print(team)
                if PRODUCTION:
                    ghc=GitHubConnector(self.cfg.get_api_key(), TEAM_REPO_PREFIX+str(team)+"/main", TEAM_REPO_PREFIX+str(team))
                else:
                    ghc=GitHubConnector(self.cfg.get_api_key(), self.cfg.get_repo(), self.cfg.get_organisation())

                result = ghc.create_issue(title='Feedback on week {} project progress'.format(WEEK), msg=feedback, assignee=None)
                if result == False:

                    # Have to mail no_issue_tracker
                    TA = tutor_map[team][1]
                    student_mails=[]
                    mail_message=no_issue_tracker[team]
                    for student in teams_to_check[team]:
                        student_mails.append(student_details[student][0])
                    self.mail_feedback(mail_message, student_mails, TA)

                time.sleep(SLEEP_TIME)

    def mail_feedback(self, message, student_mails, TA_EMAIL):

        server_ssl = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server_ssl.ehlo()
        server_ssl.login(GMAIL_USER, GMAIL_PASSWORD)

        mail_subject=message_template["week{}".format(WEEK)]["mail_subject"]

        mail_message = '{}'.format(message)

        if PRODUCTION:
            toaddr = student_mails
            cc_emails = [MODULE_EMAIL, TA_EMAIL]
        else:
            toaddr = [TEST_EMAIL]
            cc_emails = []

        mail_message = "To: %s" % ', '.join(toaddr) + "\r\n" + \
                       "CC: %s" % ', '.join(cc_emails) + "\r\n" + \
                        mail_message

        toaddr = toaddr + cc_emails
        print(toaddr,  student_mails, mail_message)

        mail = server_ssl.sendmail(GMAIL_USER, toaddr, mail_message)
        time.sleep(SLEEP_TIME)
        server_ssl.close()

    def get_feedback_message(self, teams_to_check, tutor_map, audit_details, args, end_datetime):

        message = message_template["week{}".format(WEEK)]


        
        message["indiv"]

        feedback_messages={}
        no_issue_tracker={}
        no_team_repo={}
        no_team_repo_list=[]

        for team, students in teams_to_check.items():
                
            final_message=""

            final_message+=message["subject"].format(LINK2)

            # Creating team feedback message
            team_feedback=[]
            team_index=audit_details.index[audit_details['Team']==team][0]

            no_team_repo[team]=message["no_team_repo"].format(team, LINK1.format(TEAM_REPO_PREFIX,team), LINK2, COURSE, end_datetime)

            # Team Repo created
            if int(audit_details["Team_Repo"][team_index]) == 0:
                team_feedback+=[" ", message["not_done"]]
                no_team_repo_list.append(team)
            else:
                team_feedback+=[message["x_mark"], message["done"]]

            # PR sent to upstream
            if int(audit_details["Team_PR"][team_index])>=1:
                team_feedback+=[message["x_mark"], AB3, AB4, message["done"]]
            else:
                team_feedback+=[" ", AB3, AB4, message["not_done"]]

            # autopublish
            try:
                if len(audit_details["Auto_Publish"][team_index])>=1:
                    team_feedback+=[message["x_mark"], message["done"]]
            except:
                team_feedback+=[" ", message["not_done"]]

            # UI.png
            if int(audit_details["UI_PNG"][team_index]) == 0:
                team_feedback+=[" ", message["not_done"]]
            else:
                team_feedback+=[message["x_mark"], message["done"]]


            # UG, DG
            user_guide_done, dev_guide_done = False, False
            for student in students:
                indiv_index=audit_details.index[audit_details['Student']==student][0]
                if int(audit_details['UG'][indiv_index]) >= 1:
                    user_guide_done=True
                if int(audit_details['DG'][indiv_index]) >= 1:
                    dev_guide_done=True

            if user_guide_done:
                team_feedback+=[message["x_mark"], message["done"]]
            else:
                team_feedback+=[" ", message["not_done"]]

            if dev_guide_done:
                team_feedback+=[message["x_mark"], message["done"]]
            else:
                team_feedback+=[" ", message["not_done"]]

            if int(audit_details["Git tag"][team_index]) == 0:
                team_feedback+=[" ", message["not_done"]]
            else:
                team_feedback+=[message["x_mark"], message["done"]]


            final_message+=message["team"].format(*team_feedback)




            # Issue tracker not enabled message for all students
            no_issue_tracker[team]=message["no_issue_tracker"].format(team, LINK1.format(TEAM_REPO_PREFIX,team), LINK2, COURSE, end_datetime)



            # Creating individual feedback messageer

            for student in students:
                indiv_message=message["indiv"]
                if PRODUCTION:
                    indiv_feedback=[student]
                else:
                    indiv_feedback=[DUMMY]

                indiv_index=audit_details.index[audit_details['Student']==student][0]

                if (int(audit_details["DG"][indiv_index])>=1) or (int(audit_details["UG"][indiv_index])>=1) or \
                        (int(audit_details["AboutUs"][indiv_index])>=1) or (int(audit_details["README"][indiv_index])>=1) or \
                        (int(audit_details["Java"][indiv_index])>=1):
                    indiv_feedback+=[message["x_mark"], message["done"]]
                else:
                    indiv_feedback+=[" ", message["not_done"]]

                if int(audit_details["Peer_Review"][indiv_index])==0:
                    indiv_feedback+=[" ", message["not_done"]]
                else:
                    indiv_feedback+=[message["x_mark"], message["done"]]


                if (int(audit_details["DG"][indiv_index])>=1) or (int(audit_details["UG"][indiv_index])>=1) or \
                        (int(audit_details["AboutUs"][indiv_index])>=1) or (int(audit_details["README"][indiv_index])>=1):
                    indiv_feedback+=[message["x_mark"], message["done"]]
                else:
                    indiv_feedback+=[" ", message["not_done"]]

                if (int(audit_details["Java"][indiv_index])>=1):
                    indiv_feedback+=[message["x_mark"], message["done"]]
                else:
                    indiv_feedback+=[" ", message["not_done"]]

                if (int(audit_details["Photo"][indiv_index])>=1):
                    indiv_feedback+=[message["x_mark"], student, message["done"]]
                else:
                    indiv_feedback+=[" ", student, message["not_done"]]

                final_message+= message["indiv"].format(*indiv_feedback)
            
            if PRODUCTION:
                final_message+=message["tutor"].format(tutor_map[team][0], COURSE, end_datetime)
            else:
                final_message+=message["tutor"].format(DUMMY, COURSE, end_datetime)
            feedback_messages[team]=final_message
        return feedback_messages, no_team_repo, no_issue_tracker, no_team_repo_list

    def read_audit_details(self, args):
        """
        Read the audit details stored in csv as pandas dataframe
        """
        user_audit_details = parsers.csvparser.get_pandas_list(args.audit_csv)
        return user_audit_details


    def check_if_PR_sent(self, team_list, args, start_datetime, end_datetime):

        team_PR=[]
        for repo in ADDRESSBOOK_REPO:
            repository =  Github(self.cfg.get_api_key()).get_repo(repo)
            for pull_request in repository.get_pulls(state="open", sort="updated", direction="desc"):
                try:
                    if (pull_request.created_at<=end_datetime) and (pull_request.created_at>=start_datetime):
                        pull_request_login = pull_request.user.login.lower()
                        pull_request_title = pull_request.title[:7].lower()
                        title_prefix = re.search('\[{}..?-.\]'.format(args.day.lower()), pull_request_title).group()
                        team_PR.append(title_prefix.lower()[1:-1])
                except:
                    continue
        return team_PR

    def check_autopublishing(self, team_list, args):
        
        autopublished_teams={}

        for team, students in team_list.items():
            website_url="https://"+TEAM_REPO_PREFIX+str(team)+".github.io/main"
            socket.setdefaulttimeout( 23 )  # timeout in seconds
            url = website_url
            try :
                response = urlopen( url )
            except HTTPError as e:
                print('team: '+team+', the server couldn\'t fulfill the request. Reason:', str(e.code))
            except URLError as e:
                print('team: '+team+ 'We failed to reach a server. Reason:', str(e.reason))
            else :
                html = response.read()
                autopublished_teams[team]=website_url
        return autopublished_teams

    def check_file_changes(self, repositories, team_list, args, start_datetime, end_datetime):
        """
        Counts the number of changes made by student for each required files.
        :param repositories: PyGitHub repository objects of all the team's repositories (teams which have repos created)
        :param team_list: dictionary(key=teams, value=list of students in the team) of valid teams in that week
        :return student_* : dictionary(key=student, value=count of file changed)
        """

        student_DGs,student_UGs=defaultdict(lambda: 0), defaultdict(lambda: 0)
        student_About_Us, student_Readme=defaultdict(lambda: 0), defaultdict(lambda: 0)
        student_java_code, student_PR=defaultdict(lambda: 0), defaultdict(lambda: 0)
        student_photo=defaultdict(lambda: 0)
        ui_team=defaultdict(lambda: 0)

        peer_review_students=set()

        for team, students in team_list.items():
            repo = self.team_repo_mapping[team]
            try:
                repo.full_name
            except:
                continue

            for pull_request in repo.get_pulls(state="all", sort="updated", direction="desc"):
                try:
                    pull_request_login = pull_request.user.login.lower()
                    print(pull_request_login)

                    if (pull_request.created_at<=end_datetime) and (pull_request.created_at>=start_datetime):


                        # Peer Review:
                        for comment in pull_request.get_issue_comments():
                            if (pull_request.user.login != comment.user.login): 
                                peer_review_students.add(comment.user.login.lower())
                        for comment in pull_request.get_comments():
                            if (pull_request.user.login != comment.user.login):
                                peer_review_students.add(comment.user.login.lower())
                        for comment in pull_request.get_review_comments():
                            if (pull_request.user.login != comment.user.login):
                                peer_review_students.add(comment.user.login.lower())
                        for comment in pull_request.get_reviews():
                            if (pull_request.user.login != comment.user.login):
                                peer_review_students.add(comment.user.login.lower())


                        for file in pull_request.get_files():
                            filename = file.filename
                            if int(file.changes)>0:

                                if (pull_request_login is not None):
                                    student_PR[pull_request_login]+=1

                                if (pull_request.merged==True):
                                    if (DEVELOPER_GUIDE in file.filename) and (pull_request_login is not None):
                                        student_DGs[pull_request_login]+=1
                                    elif (USER_GUIDE in file.filename) and (pull_request_login is not None):
                                        student_UGs[pull_request_login]+=1
                                    elif (ABOUT_US in file.filename) and (pull_request_login is not None):
                                        student_About_Us[pull_request_login]+=1
                                    elif (README in file.filename) and (pull_request_login is not None):
                                        student_Readme[pull_request_login]+=1
                                    elif ((JAVA in file.filename) or (FXML in file.filename)) and (pull_request_login is not None):
                                        student_java_code[pull_request_login]+=1

                            if (UI_PNG_SUBSTRINGS[0] in filename.lower()) and (UI_PNG_SUBSTRINGS[1] in filename.lower()):
                                ui_team[team]+=1
                            elif (PNG in filename.lower()):
                                student_photo[filename.rsplit(".",1)[0].split("/")[-1].lower().strip()]+=1

                except:
                    continue

            for commit in repo.get_commits(since=start_datetime, until=end_datetime):
                if commit.commit.author.date >= start_datetime:
                    for file in commit.files:
                        if (PNG in file.filename.lower()):
                            student_photo[file.filename.rsplit(".",1)[0].split("/")[-1].lower().strip()]+=1

        return student_DGs, student_UGs, student_About_Us, student_Readme, student_java_code, ui_team, student_photo, peer_review_students

    def check_team_forks(self, repositories):
        
        students_with_forks=[]
        for repo, students in repositories:
            forks_made=[fork.full_name.split("/")[0] for fork in repo.get_forks()]
            students_with_forks+=forks_made

        students_with_forks = [student.lower() for student in students_with_forks]
        return students_with_forks

    def check_team_repo_setup(self, args):

        if parsers.common.are_files_readable(args.csv):
            teams_to_check, student_details=self.extract_team_info(args.csv, args.day)
            teams_with_repo, teams_without_repo, repositories=self.check_repo_existence(teams_to_check)
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

    def load_tutor_map(self, csv_file):
        data=parsers.csvparser.get_rows_as_list(csv_file)
        tutor_map={}
        for datum in data:
            tutor_map[datum[0]]=(datum[1].strip(), datum[2].strip())
        return tutor_map


    def check_repo_existence(self, teams_to_check):
        
        teams_with_repo, teams_without_repo={}, {}
        repo_objects = []
        self.team_repo_mapping={}
        for team, students in teams_to_check.items():
            repository=TEAM_REPO_PREFIX+str(team)+"/main"
            try:
                repository =  Github(self.cfg.get_api_key()).get_repo(repository)
                repository_name = repository.full_name
                repo_objects.append((repository, students))

                # Checking git tags

                teams_with_repo[team]= students
                self.team_repo_mapping[team]=repository

            except GithubException as e:
                logging.error('Team repo for {} not found!'.format(team))
                teams_without_repo[team]=students
        return teams_with_repo, teams_without_repo, repo_objects

    def check_milestones(self, local_milestones):


    def check_jar_releaseTag_existence(self, teams_to_check, start_datetime, end_datetime):
        # teams_with_release, teams_without_release, teams_with_jar, teams_without_jar = {}, {}, {}, {}
        teams_with_tag=[]
        teams_with_issue_label=[]
        teams_with_milestones=[]
        for team, students in teams_to_check.items():
            if team in self.team_repo_mapping.keys():
                repository = self.team_repo_mapping[team]

                
                repository_labels = repository.get_labels()
                repository_milestones = repository.get_milestones()

                # Note labels for the repository
                for label in repository_labels:
                    if (TYPE in label.name.lower()) and (PRIORITY in label.name.lower()):
                        teams_with_issue_label.append(team)

                # Note milestones for the repository
                local_milestones=[]
                for milestone in repository_milestones:
                    local_milestones.append(milestone.title.lower())
                
                if (self.check_milestones(local_milestones)):
                    teams_with_milestones.append(team)

                # MILESTONE_SET=False
                # for milestone_to_check in 

                # print()

                repository_releases = repository.get_releases()
                tags = repository.get_tags()
                for tag in tags:
                    if tag.name.lower() == TAG:
                        teams_with_tag.append(team)
        exit()
        return teams_with_tag

                # for release in repository_releases :
                #     print(release.published_at)
                #     if release.published_at <= end_datetime and release.published_at >= start_datetime :
                #         if release.tag_name is not None :
                #             print(release.tag_name)
                #             teams_with_release[team] = students
                #         if release.tarball_url is not None or release.zipball_url is not None :
                #             teams_with_jar[team] = students
                # if teams_with_release.get(team, None) is None :
                #     teams_without_release[team] = students
                # if teams_with_jar.get(team, None) is None :
                #     teams_without_jar[team] = students
        # return teams_with_release, teams_without_release, teams_with_jar, teams_without_jar

    def write_week_to_csv(self, team_list, teams_with_repo, teams_with_PR, student_with_forks, student_DGs, \
                            student_UGs, student_About_Us, student_Readme, student_java_code, ui_team, \
                            student_photo, peer_review_students, autopublished_teams, teams_with_tag, day):

        output_path = OUTPUT_DIR+"/week_{}/".format(WEEK)
        output_file = output_path+"week_{}_audit_day{}.csv".format(WEEK, day)

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        wr = csv.writer(open(output_file, 'w'), delimiter=',', 
                            quoting=csv.QUOTE_ALL)
        wr.writerow(CSV_HEADER)
        for team, students in team_list.items():
            ["Auto_Publish", "UI_PNG", "Fork", "DG", "UG", "AboutUs", "README", "Java", "Peer_Review", "Photo"]
            for student in students:
                to_print=[]
                to_print.append(student)
                to_print.append(team)
                to_print.append(int(team in teams_with_repo))
                to_print.append(int(team.lower() in teams_with_PR))
                if team in autopublished_teams.keys():
                    to_print.append(autopublished_teams[team])
                else:
                    to_print.append('')
                to_print.append(int(ui_team[team] > 0))
                to_print.append(int(team in teams_with_tag))
                to_print.append(int(student in student_with_forks))
                to_print.append(int(student_DGs[student] > 0))
                to_print.append(int(student_UGs[student] > 0))
                to_print.append(int(student_About_Us[student] > 0))
                to_print.append(int(student_Readme[student] > 0))
                to_print.append(int(student_java_code[student] > 0))
                to_print.append(int(student in peer_review_students))
                to_print.append(int(student_photo[student] > 0))
                wr.writerow(to_print)

        return output_file