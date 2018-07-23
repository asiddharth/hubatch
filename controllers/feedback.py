"""
Creating and Posting feedback for teams/students
"""
from .common import BaseController
from connectors.github import GitHubConnector

import parsers
import sys
import datetime
import ast
import logging, time, re, argparse, json
from collections import defaultdict
from pathlib import Path


DELIVERABLES = "controllers/data/deliverables.json"
CHECK_AT = ["AB1", "AB3", "AB2", "AB4"]
ORGANIZATION = "nus-cs2103-AY1718S2"
REPO_PREFIX = "addressbook-level"
REVIEWED_LABELS = ['Reviewed', 'Kudos', 'ReviewedInTutorial', 'AcceptedWithMinimalReview']

with open(DELIVERABLES, 'r') as f:
    deliverables= json.load(f)

class CreateFeedback(BaseController):
    def __init__(self, cfg):
        self.cfg = cfg

    def setup_argparse(self, subparsers):
        """
        Sets up the subparser for Feedback tools
        """
        parser = subparsers.add_parser('create-feedback', help='Creating weekly feedback')
        create_feedback_parser = parser.add_subparsers(help='generate feedback message')
        # post_feedback_parser = parser.add_subparsers(help='post generated feedback messages')
        self.setup_create_feedback(create_feedback_parser)

    def setup_create_feedback(self, subparsers):

        example_text = ''''''

        parser = subparsers.add_parser('compile', help='compile details of submissions into message per team'
                                    ,epilog=example_text
                                    ,formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument('-csv', type=str,
                            help='filename of the CSV containing a list of GitHub usernames, team affiliations, day')
        parser.add_argument('-w', '--week', type=int,
                            help='Week number of the course')
        parser.add_argument('-d', '--day', type=str,
                            help='Deadline day of the week')
        parser.set_defaults(func=self.count_deliverables)

    def count_deliverables(self, args):
        """
		Counts team and individual statistics for deliverables in a week by a team
        """	
        teams_to_check = self.extract_relevant_info(args.csv, args.day)

        cat1_done, cat2_done, call_done = defaultdict(list), defaultdict(list), defaultdict(list)
        cat1_not_done, cat2_not_done, call_not_done = defaultdict(list), defaultdict(list), defaultdict(list)
        indiv_done, indiv_not_done = defaultdict(list), defaultdict(list)


        for questions in deliverables["week{}".format(args.week)]["team_atleast1"]:
            question = self.get_consistent_PR_label(questions)

            for team, students in teams_to_check.items():
                if len(self.count_atleast(team, students, question, args.week, args.day)) >=1:
                    cat1_done[team].append(questions)
                else:
                    cat1_not_done[team].append(questions)

        for questions in deliverables["week{}".format(args.week)]["team_atleast2"]:
            question = self.get_consistent_PR_label(questions)

            for team, students in teams_to_check.items():
                if len(self.count_atleast(team, students, question, args.week, args.day)) >=2:
                    cat2_done[team].append(questions)
                else:
                    cat2_not_done[team].append(questions)

        for questions in deliverables["week{}".format(args.week)]["team_all"]:
            question = self.get_consistent_PR_label(questions)

            for team, students in teams_to_check.items():
                if len(self.count_atleast(team, students, question, args.week, args.day)) >=4:
                    call_done[team].append(questions)
                else:
                    call_not_done[team].append(questions)

        for questions in deliverables["week{}".format(args.week)]["individual"]:
            question = self.get_consistent_PR_label(questions)

            for team, students in teams_to_check.items():
                submitted_students = self.count_atleast(team, students, question, args.week, args.day)
                for student in students:
                    if student in submitted_students:
                        indiv_done[student].append(questions)
                    else:
                        indiv_not_done[student].append(questions)

        # self.save_data(teams_to_check, cat1, cat2, call, indiv)

        feedbacks = self.generate_feedback_message(teams_to_check, cat1_done, cat1_not_done,
                                                   cat2_done, cat2_not_done, call_done, call_not_done, 
                                                   indiv_done, indiv_not_done)
        self.post_feedback(feedbacks, args.week)



    # def save_data(teams_to_check, cat1, cat2, call, indiv):
    #     Header = ["student", "team", "submitted", "atleast1", "atleast2", "all"]


    def get_submitted_list(self, filename, student):
        data = parsers.csvparser.get_rows_as_dict(filename)
        return ast.literal_eval(data[student][0])

    def check_if_submitted(self, student, question, week, day):
        for loc in CHECK_AT:
            checking_location = "output/"+loc+"/week_{}/".format(week) \
                                +"student_PRs_done_week{}_{}_day{}.csv".format(week, loc, day)
            
            if Path(checking_location).is_file():
                question_submitted = self.get_submitted_list(checking_location, student)
            
                if question in question_submitted:
                    return True

        return False

    def count_atleast(self, team, students, question, week, day):
        student_submitted=[]
        for student in students:
            if self.check_if_submitted(student, question, week, day):
                student_submitted.append(student)
        return student_submitted

    def get_consistent_PR_label(self, PR_label):
        return PR_label.lower()

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


    def post_feedback(self, feedbacks, week):

        ghc=GitHubConnector(self.cfg.get_api_key(), self.cfg.get_repo(), self.cfg.get_organisation())

        for team, feedback in feedbacks.items():
            print(team)
            ghc.create_issue(title='PR Submission feedback for week {}'.format(week), msg=feedback, assignee=None)
            time.sleep(2)

    def generate_feedback_message(self, teams_to_check, cat1_done, cat1_not_done,
                                        cat2_done, cat2_not_done, call_done, call_not_done, 
                                        indiv_done, indiv_not_done):

        feedbacks={}
        for team, students in teams_to_check.items():
            feedback_message = ""
            team_PR_done, team_PR_not_done = [], []

            feedback_message = feedback_message + "@Team-{}: \n\nPRs submitted for team consideration: ".format(team)
            
            FLAG=0
            for question in (set(cat1_done[team]+cat2_done[team]+call_done[team])):
                feedback_message+= question
                FLAG=1

            feedback_message+= " None\n" if FLAG==0 else " \n"
            feedback_message+="PRs pending submission for team consideration: "

            FLAG=0
            for question in (set(cat1_not_done[team]+cat2_not_done[team]+call_not_done[team])):
                feedback_message+= question
                FLAG=1

            feedback_message+= " None\n\n" if FLAG==0 else " \n\n"
                

            for student in students:
                feedback_message+= "@Student: \n\nPRs sucessfully submitted: "

                FLAG=0
                for question in (set(indiv_done[student])):
                    feedback_message+= question
                    FLAG=1

                feedback_message+= " None\n" if FLAG==0 else " \n"

                feedback_message+="PRs pending submission: "

                FLAG=0
                for question in (set(indiv_not_done[student])):
                    feedback_message+= question
                    FLAG=1

                feedback_message+= " None\n\n" if FLAG==0 else " \n\n"

                feedbacks[team] = feedback_message

        return feedbacks

