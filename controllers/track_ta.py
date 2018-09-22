"""
Useful tools for managing TAs
"""
from .common import BaseController
from connectors.github import GitHubConnector

import parsers
import smtplib
import sys, csv, os, ast, json
import datetime
import logging, time, re, argparse
from collections import defaultdict

#############################################################
COURSE = "CS2113"
ORGANIZATION = "nusCS2113-AY1819S1"
GMAIL_USER = 'cs2113.bot@gmail.com'  
GMAIL_PASSWORD = 'cs2113.bot.feedback'
TEST_EMAIL = "hdevamanyu@student.nitw.ac.in"
TEST_EMAIL_2 = "devamanyu@gmail.com"
LECTURER_EMAIL = "anarayan@comp.nus.edu.sg"
HEAD_TA_EMAIL = "slewyh@comp.nus.edu.sg"

STERNER_MAIL = False
PRODUCTION = True
#############################################################


REPO_PREFIX = "addressbook-level"
ACCEPTED_LABELS = ["reviewed", "kudos!!", "accepted w/ minimal review"]
CSV_HEADER = ["TA", "Pending", "Created_at", "Days_before"]
OUTPUT_DIR = "./output/"
LEVELS = ["1", "2", "3", "4"]
MESSAGE_TEMPLATE = "controllers/data/message_template.json"
SLEEP_TIME = 3

with open(MESSAGE_TEMPLATE, 'r') as f:
    message_template=json.load(f)

class TADuties(BaseController):
    def __init__(self, cfg):
        self.cfg = cfg

    def setup_argparse(self, subparsers):
        """
        Sets up the subparser for PRDetector
        """
        parser = subparsers.add_parser('TA_duties', help='TA management tools')
        track_ta_subparsers = parser.add_subparsers(help='track reviews of TAs')
        self.setup_check_PR(track_ta_subparsers)
        self.setup_post_reminder(track_ta_subparsers)

    def setup_check_PR(self, subparsers):

        parser = subparsers.add_parser('track-TA', help='track review status of TAs in Addressbook')
        parser.add_argument('-csv', type=str,
                            help='filename of the CSV containing list of tutors')
        parser.add_argument('-w', '--week', type=str,
                            help='Week number')
        parser.set_defaults(func=self.track_TA_command)

    def setup_post_reminder(self, subparsers):

        parser = subparsers.add_parser('post-reminder', help='send reminder to TAs regarding Pending reviews')
        parser.add_argument('-csv', type=str,
                            help='filename of the CSV containing list of tutors')
        parser.add_argument('-pending_list', type=str,
                            help='filename of the CSV containing tutors with pending reviews')
        parser.add_argument('-w', '--week', type=str,
                            help='Week number')
        parser.set_defaults(func=self.remind_TA)

    def remind_TA(self, args):
        """
        Creates and emails pending list of PRs to each TA
        """

        logging.debug('Reading audit from csv: %s', args.csv)

        ta_reviews = self.read_pending_reviews(args)
        list_of_TAs, _ = self.extract_relevant_info(args.csv)
        reminder_messages = self.get_feedback_message(list_of_TAs, ta_reviews, args)
        self.email_TA(list_of_TAs, reminder_messages)


    def email_TA(self, list_of_TAs, reminder_message):

        if PRODUCTION:
            response = input("\n\nALERT!!\n\nAre you sure to send actual emails? [Y/n]")
            response = response.lower()
            if "n" in response:
                exit()

        server_ssl = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server_ssl.ehlo()
        server_ssl.login(GMAIL_USER, GMAIL_PASSWORD)

        mail_subject=message_template['ta-reminder']["mail_subject"].format(COURSE)

        for name, email, gid in list_of_TAs:
            if gid in reminder_message.keys():
                mail_message = 'Subject: {}\n\n{}'.format(mail_subject, reminder_message[gid])

                print(name, email)
                print(mail_message)

                toaddr = [email if PRODUCTION else TEST_EMAIL]
                
                if STERNER_MAIL:
                    cc_emails = [LECTURER_EMAIL, HEAD_TA_EMAIL]
                    mail_message = "To: %s" % ', '.join(toaddr) + "\r\n" + \
                                   "CC: %s" % ', '.join(cc_emails) + "\r\n" + \
                                    mail_message

                    toaddr = toaddr + cc_emails

                mail = server_ssl.sendmail(GMAIL_USER, toaddr, mail_message)
                time.sleep(SLEEP_TIME)
        server_ssl.close()


    def get_feedback_message(self,list_of_TAs, ta_reviews, args ):
        
        reminder_message={}
        for name, email, gid in list_of_TAs:
            index = ta_reviews.index[ta_reviews['TA']==gid][0]
            try:
                pending_reviews = ast.literal_eval(ta_reviews["Pending"][index])
                pending_reviews_days_before = ast.literal_eval(ta_reviews["Days_before"][index])
            except:
                continue

            number_of_pending_reviews = len(pending_reviews)
            number_of_days_before = len(pending_reviews_days_before)
            assert(number_of_pending_reviews == number_of_days_before)

            if number_of_pending_reviews>0:

                review_list=""
                for reviews, days_before in zip(pending_reviews, pending_reviews_days_before):
                    review_list+="\n "
                    review_list+= str(reviews)
                    review_list+= "   : created {} day(s) ago.".format(str(days_before))

                if STERNER_MAIL:
                    reminder_message[gid]=message_template['ta-reminder']['mail_body_sterner'].format(name, review_list, COURSE)
                else:
                    reminder_message[gid]=message_template['ta-reminder']['mail_body'].format(name, review_list, COURSE)
        return reminder_message

    def read_pending_reviews(self, args):

        ta_review_details = parsers.csvparser.get_pandas_list(args.pending_list)
        return ta_review_details

    def track_TA_command(self, args):
        logging.debug('Tracking non-reviews PRs in Addressbook')
        logging.debug('CSV datafile: %s', args.csv)
        if parsers.common.are_files_readable(args.csv):
            reviews_not_done, reviews_not_done_date, reviews_not_done_days, list_of_TAs = self.check_PR_reviews(args)
            output_file=self.write_week_to_csv(reviews_not_done, reviews_not_done_date, reviews_not_done_days, list_of_TAs, args)
        else:
            sys.exit(1)


    def check_PR_reviews(self, args):

        list_of_TAs, reviews_not_done = self.extract_relevant_info(args.csv)

        reviews_not_done_date = defaultdict(list)
        reviews_not_done_days = defaultdict(list)

        for level in LEVELS:
            repository_name = REPO_PREFIX+str(level)
            repository = GitHubConnector(self.cfg.get_api_key(), ORGANIZATION+"/"+repository_name, ORGANIZATION).repo
            reviews_not_done, reviews_not_done_date, reviews_not_done_days = self.get_PR_review_info(list_of_TAs, reviews_not_done, \
                    reviews_not_done_date, reviews_not_done_days, repository, args)

        return reviews_not_done, reviews_not_done_date, reviews_not_done_days, list_of_TAs

    def get_PR_review_info(self, list_of_TAs, reviews_not_done, reviews_not_done_date, reviews_not_done_days, repository, args):

        TA_github_ids=[]
        for name, email, gid in list_of_TAs:
            TA_github_ids.append(gid)

        for pull_request in repository.get_pulls(state="all", sort="updated", direction="desc"):
            print(pull_request.title)

            try:
                if (not pull_request.title[:2].lower() == '[w') or (int(pull_request.title[2]) > int(args.week)):
                    continue
            except:
                continue

            
            for ta in pull_request.assignees:
                if ta.login.lower() in TA_github_ids:
                    REVIEW_DONE = False
                    for label in pull_request.labels:
                        if label.name.lower() in ACCEPTED_LABELS:
                            REVIEW_DONE = True
                    
                    if not REVIEW_DONE:
                        for comment in pull_request.get_reviews():
                            if comment.user.login == ta.login.lower():
                                REVIEW_DONE = True
                                break

                    if not REVIEW_DONE:
                        reviews_not_done[ta.login].append(pull_request.html_url)
                        reviews_not_done_date[ta.login].append(pull_request.created_at)
                        reviews_not_done_days[ta.login].append((datetime.datetime.now()-pull_request.created_at).days)

        return reviews_not_done, reviews_not_done_date, reviews_not_done_days

    def extract_relevant_info(self, csv_file):
        user_list = parsers.csvparser.get_rows_as_list(csv_file)
        list_of_TAs = set(map(lambda x: (x[0].strip(), x[2].strip().lower(), x[3].strip().lower()), user_list[1:]))

        reviews_not_done=defaultdict(list)

        return list_of_TAs, reviews_not_done

    def write_week_to_csv(self, reviews_not_done, reviews_not_done_date, reviews_not_done_days, list_of_TAs, args) :

        output_path = OUTPUT_DIR+"/week_{}/".format(args.week)
        output_file = output_path+"week_{}_pending_ta_reviews.csv".format(args.week)

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        wr = csv.writer(open(output_file, 'w'), delimiter=',', 
                            quoting=csv.QUOTE_ALL)
        wr.writerow(CSV_HEADER)
        for name, email, gid in list_of_TAs:
            to_print=[]
            to_print.append(gid)
            if gid in reviews_not_done.keys():
                to_print.append(reviews_not_done[gid])
                to_print.append(reviews_not_done_date[gid])
                to_print.append(reviews_not_done_days[gid])
            else:
                to_print.append([])
            wr.writerow(to_print)
        return output_file