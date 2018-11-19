"""
Issue-related tasks
"""
from pkg_resources import issue_warning

from .common import BaseController
from github import Github, GithubObject, GithubException
from pathlib import Path
import parsers
import pickle
import time,sys
import os
import re
import csv
import random
from collections import defaultdict
from connectors import GitHubConnector

import logging, re, time, json


###############################################################
FROMREPO = "nus-cs2103-AY1819S1/pe-results"
FROMREPO_DUMMY = "DummyTA1/main"

FROMREPOORIGINAL = "nus-cs2103-AY1819S1/pe"

GITHUB_ID_COLUMN_INDEX=2 # mapping details: github id
TEAM_ASSIGNED_COLUMN_INDEX=5 # mapping details: assigned team
Production = False
###############################################################
REF_TEMPLATE = '\n\n<hr>\n<sub>[original: {}#{}]</sub>'

DUPLICATE_STRING = "Duplicate of #"
OUTPUT_PATH = "./output/PE-2/"
OUTPUT_DIR = "./output/"
PE_FILE = "pe_2.p"
DUMMY = "dummy"
DUMMY_TOREPO = "DummyTA1/main"
MESSAGE_TEMPLATE = "controllers/data/message_template.json"
Severity_Levels = {"low":0, "medium":1, "high":2}
CSV_HEADER = ["issue_number", "multiple_responses", "multiple_severity",\
              "multiple_type", "response_missing", "accepted_no_assignees", \
              "rejected_no_comments", "severity_downgraded_no_comments", \
              "duplicate_but_no_parent", "is_parent_duplicate", "parent_severity_lesser"]

TO_REPO_TA = "nus-cs2103-AY1819S1/pe-tutor-processing"
_HEX = '0123456789ABCDEF'


with open(MESSAGE_TEMPLATE, 'r') as f:
    message_template=json.load(f)

class PeProcessing(BaseController):
    def __init__(self, ghc, cfg):
        self.ghc = ghc
        self.cfg = cfg
        self.gh = Github(self.cfg.get_api_key())

    def setup_argparse(self, subparsers):
        """
        Sets up the subparser for issue blaster
        """
        parser = subparsers.add_parser('pe-process', help='GitHub issue management tools')
        issue_subparsers = parser.add_subparsers(help='name of tool to execute')
        self.process_pe_issues(issue_subparsers)
        self.post_pe_issues(issue_subparsers)
        self.post_into_ta_repository(issue_subparsers)


    def post_pe_issues(self, subparsers):
        parser = subparsers.add_parser('post-checks', help='posts issue checks')
        parser.add_argument('-audit_csv', '--audit', metavar='csv', type=str,
                            help='filename of CSV containing issue check audits')
        parser.set_defaults(func=self.post_issue_checks)

    def process_pe_issues(self, subparsers):
        parser = subparsers.add_parser('check_issue', help='performs issue checks')
        parser.add_argument('-m', '--mapping', metavar='csv', type=str,
                            help='filename of CSV containing the title tag mapping')
        parser.set_defaults(func=self.check_issue_command)

    def post_into_ta_repository(self, subparsers):
        parser = subparsers.add_parser('post-ta', help='posts to TA repository')
        parser.add_argument('-tutor_map', '--tutor_map', metavar='csv', type=str,
                            help='filename of CSV containing the TA-team mapping')
        parser.add_argument('-team_map', '--team_map', metavar='csv', type=str,
                            help='filename of CSV containing the team mapping')
        parser.set_defaults(func=self.post_ta_issue_checks)



    def get_random_colour(self):
        return ''.join(random.choice(_HEX) for _ in range(6))


    def add_labels_to_repository(self, repo, labels):
        try:
            self.gh = Github(self.cfg.get_api_key())
            repo = self.gh.get_repo(repo)

            for label in labels:
                new_color = self.get_random_colour()
                try:
                    repo.create_label(label, new_color, "")
                except:
                    continue
        except GithubException as e:
            GitHubConnector.log_exception(e.data)


    def get_labels_from_repository(self, repo):

        try:
            self.gh = Github(self.cfg.get_api_key())
            repo = self.gh.get_repo(repo)
            return repo.get_labels()
        except GithubException as e:
            GitHubConnector.log_exception(e.data)
            return []

    def load_tutor_map(self, csv_file):
        data=parsers.csvparser.get_rows_as_list(csv_file)
        tutor_map={}
        for datum in data:
            tutor_map[datum[0]]=(datum[1].strip(), datum[2].strip())
        return tutor_map

    def extract_team_info(self, csv_file):

        user_list=parsers.csvparser.get_rows_as_list(csv_file)[1:]
        users_to_check=list(map(lambda x: [x[-2].lower().strip(), x[-3], x[-4], x[0], x[-1]], user_list))

        team_list=defaultdict(list)
        student_details={}
        for user, team, email, name, team_no in users_to_check :
            team_list[team+"-"+team_no[-1]].append(user)
            student_details[user]=(email, name)
        return team_list, student_details

    def create_issue_body(self, issue, team_members) :
        issue_body = issue.body
        for comment in issue.get_comments() :
            issue_body += "\n <hr> \n ** Comment by `" + comment.user.name + "` \n"
            issue_body += comment.body
        if Production :
            issue_body += REF_TEMPLATE.format(FROMREPO, issue.number)
        else :
            issue_body += REF_TEMPLATE.format(FROMREPO_DUMMY, issue.number)
        issue_body += "<sub> assignees: "
        for member in team_members :
            issue_body += "`" + member + "`"
        issue_body += "</sub>"
        issue_body += "\n\n**Tutor to check:**\n"
        issue_body += "- [] duplicate status \n"
        issue_body += "- []  downgrade of severity \n"
        issue_body += "- [] justification for rejection \n"
        return issue_body


    def post_ta_issue_checks(self, args):
        from_repo_issues = pickle.load(open("./temp.p", "rb"))
        # Setting up the labels
        tutor_map = self.load_tutor_map(args.tutor_map)
        student_map = self.extract_team_info(args.team_map)
        LABEL_NAMES = list(map(lambda x : x.name, list(self.get_labels_from_repository(FROMREPO))))
        LABEL_NAMES = list(set(LABEL_NAMES))
        print("Adding Labels")
        # Create new labels in TOREPO
        if Production:
            self.add_labels_to_repository(TO_REPO_TA, LABEL_NAMES)
        else:
            self.add_labels_to_repository(DUMMY_TOREPO, LABEL_NAMES)
        print("Added Labels")

        # All labels from TO_REPO
        if Production:
            to_repo_label_objects = self.get_labels_from_repository(TO_REPO_TA)
        else:
            to_repo_label_objects = self.get_labels_from_repository(DUMMY_TOREPO)

        LABEL_OBJ = {}
        for label in to_repo_label_objects:
            LABEL_OBJ[label.name]=label

        current_issues = {}
        for issue in from_repo_issues:
            current_issues[issue.number] = issue

        for idx, issue in enumerate(from_repo_issues):
            print(idx)
            try:
                from_student = issue.user.login.lower()
                labels = []

                # isSeverity = False
                # for label in issue.labels:
                #     if "sever" in label.name:
                #         isSeverity = True
                # print(isSeverity)
                #
                # # Repo severity
                # if (len(issue.labels) == 0) or (not isSeverity):
                #     labels.append(LABEL_OBJ["severity.Low"])
                # else:
                #     # For failure in label objects
                #     for label in issue.labels:
                #         try:
                #             labels.append(LABEL_OBJ[label.name])
                #         except:
                #             continue
                #
                # # Tutorial and Team
                # TUTORIAL, TEAM_NO = mapping_dict[from_student].split("-")
                # labels.append(LABEL_OBJ["tutorial.{}".format(TUTORIAL)])
                # labels.append(LABEL_OBJ["team.{}".format(TEAM_NO)])
                tutorial = ""
                team = ""
                isDuplicate = False
                parent_issue_number = None
                for label in issue.labels:
                    try:
                        labels.append(LABEL_OBJ[label.name])
                        if label.name.startswith('team') :
                            team = label.name[-1]
                        if label.name.startswith('tutorial') :
                            tutorial = label.name[-3:]
                        if label.name.lower() == "duplicate":
                            isDuplicate = True
                    except:
                        continue
                team_name = tutorial + team
                students = student_map[team_name]
                title = "[" + str(issue.number) + "]" + issue.title
                new_body = self.create_issue_body(issue, students)

                if isDuplicate:
                    for comment in issue.get_comments():
                        comment_str = comment.body.lower()
                        duplicate_str = re.search(r'duplicate\s+of\s+#([0-9]+)', comment_str)
                        if duplicate_str:
                            parent_issue_number = int(duplicate_str.group(1))
                            break
                    new_body += "\n\n**The following issue is claimed as the original:**\n\n"
                if parent_issue_number is None :
                    new_body +=  "### Missing! \n\n"
                else :
                    parent_issue = current_issues[int(parent_issue_number)]
                    new_body += self.create_issue_body(parent_issue, students)

                if Production:
                    print(TO_REPO_TA)
                    is_transferred = self.ghc.create_issue(title=title, msg=new_body, assignee=None,
                                                           labels=labels, repo=TO_REPO_TA)
                else:
                    is_transferred = self.ghc.create_issue(title=title, msg=new_body, assignee=None,
                                                           labels=labels, repo=DUMMY_TOREPO)

                if not is_transferred:
                    logging.error('Unable to create issue with idx: %s', idx)
                    print('Unable to create issue with idx: %s', idx)
                    exit()
                time.sleep(2)

            except:
                print("Crashed")
                completed = idx
                pickle.dump(from_repo_issues[completed:], open("./temp.p", "wb"))
                exit()
        return

    def post_issue_checks(self, args):
        
        # Read audit csv
        audit = self.read_audit_details(args.audit)

        # Copy all issues
        all_issues = self.get_issues_from_repository()

        # Message
        message = message_template["pe-checks"]

        # for issue in all_issues:
        # issue_obj = self.repo.get_issue(number=issue.number)


    def read_audit_details(self, path):
        user_audit_details = parsers.csvparser.get_pandas_list(path)
        return user_audit_details


    def check_issue_command(self, args):

        if parsers.common.are_files_readable(args.mapping):
            self.check_issues(args.mapping)
        else:
            sys.exit(1)

    def extract_mapping_info(self, csv_file):

        user_list=parsers.csvparser.get_rows_as_list(csv_file)[1:]
        users_to_check=list(map(lambda x: [x[GITHUB_ID_COLUMN_INDEX].lower().strip(), x[TEAM_ASSIGNED_COLUMN_INDEX]], user_list))

        mapping={}
        for user, product_team in users_to_check :
            mapping[user] = product_team
        return mapping

    def get_issues_from_repository(self):
        '''Gets issues from a specified repository'''
        try:
            self.gh = Github(self.cfg.get_api_key())
            self.repo = repo = self.gh.get_repo(FROMREPO)
            return repo.get_issues(state = "all", direction='asc')
        except GithubException as e:
            GitHubConnector.log_exception(e.data)
            return []


    def check_issues(self, mapping_file):
        '''
        Checks numerous things from one pe issues
        '''

        # Load student mapping
        mapping_dict = self.extract_mapping_info(mapping_file)

        # Load original issues
        original_issues = {}
        for orig_issue in pickle.load(open(OUTPUT_PATH+PE_FILE, "rb")):
            original_issues[int(orig_issue.number)]=orig_issue


        # Output dictionary
        audit = defaultdict(list)

        # Copy all issues
        all_issues = self.get_issues_from_repository()
        current_issues={}
        for issue in all_issues:
            current_issues[issue.number]=issue

        for issue in all_issues:

            original_issue_number = int(re.search( r'{}#(.*)]</sub>'.format(FROMREPOORIGINAL), issue.body).group(1))
            
            # Original copy of current issue
            original_issue = original_issues[original_issue_number]


            isDuplicateLabel=False 
            isResponse, isSeverity, isType=False, False, False
            isAccepted, isRejected, isSeverityDowngraded=False, False, False
            isMultipleResponse, isMultipleSeverity, isMultipleType=False, False, False
            issueSeverityOriginal = "low"
            issueSeverityCurrent = "low"
            parent_issue_number = None
            comments = issue.get_comments()

            
            for label in issue.labels:
                if label.name.lower() == "duplicate":
                    isDuplicateLabel = True
                    break
                elif "response" in label.name.lower():
                    if isResponse:
                        isMultipleResponse=True
                    isResponse = True

                    if "accepted" in label.name.lower():
                        isAccepted=True
                    elif "rejected" in label.name.lower():
                        isRejected=True

                elif "severity" in label.name.lower():
                    if isSeverity:
                        isMultipleSeverity=True
                    isSeverity = True

                    issueSeverityCurrent = label.name.split(".")[-1].lower()

                elif "type" in label.name.lower():
                    if isType:
                        isMultipleType=True
                    isType = True

            # Original issue severity label
            for label in original_issue.labels:
                if "severity" in label.name.lower():
                    issueSeverityOriginal = label.name.split(".")[-1].lower()

            # Assignees of current issue
            assignees = issue.assignees


            


            # Check conditions
            if isMultipleResponse:
                audit[issue.number].append(1)
            else:
                audit[issue.number].append(0)

            if isMultipleSeverity:
                audit[issue.number].append(1)
            else:
                audit[issue.number].append(0)

            if isMultipleType:
                audit[issue.number].append(1)
            else:
                audit[issue.number].append(0)

            if not isResponse:
                audit[issue.number].append(1)
            else:
                audit[issue.number].append(0)

            if (isAccepted) and (len(assignees) == 0):
                audit[issue.number].append(1)
            else:
                audit[issue.number].append(0)

            if (isRejected) and (issue.comments==0):
                audit[issue.number].append(1)
            else:
                audit[issue.number].append(0)

            if (Severity_Levels[issueSeverityOriginal] > Severity_Levels[issueSeverityCurrent]) and (issue.comments==0):
                audit[issue.number].append(1)
            else:
                audit[issue.number].append(0)


            
                    


            if isDuplicateLabel:

                for comment in comments:
                    comment_str = comment.body.lower()
                    duplicate_str = re.search( r'duplicate\s+of\s+#([0-9]+)', comment_str)
                    duplicate_2_str = re.search( r'dupli', comment_str)
                    if duplicate_str:
                        parent_issue_number = int(duplicate_str.group(1))
                        break


                if parent_issue_number is None:
                    # Case 1: Issue labeled dupicate but "Duplicate of #xx" not given in comments"
                    # print(isDuplicateLabel, parent_issue_number, issue.url)
                    audit[issue.number].extend([1,0,0])
                else:
                    audit[issue.number].append(0)


                    parent_issue = current_issues[int(parent_issue_number)]

                    isParentDuplicate = False
                    parentIssueSeverityCurrent = "low"

                    for label in parent_issue.labels:
                        if label.name.lower() == "duplicate":
                            isParentDuplicate = True
                        if "severity" in label.name.lower():
                            parentIssueSeverityCurrent = label.name.split(".")[-1].lower()

                    #Find parent issue's original severity
                    original_parent_issue_number = int(re.search( r'{}#(.*)]</sub>'.format(FROMREPOORIGINAL), parent_issue.body).group(1))
                    parent_original_issue = original_issues[original_parent_issue_number]
                    parentIssueSeverityOriginal = "low"

                    for label in parent_original_issue.labels:
                        if "severity" in label.name.lower():
                            parentIssueSeverityOriginal = label.name.split(".")[-1].lower()
                            break



                    if isParentDuplicate:
                        audit[issue.number].append(1)
                    else:
                        audit[issue.number].append(0)

                    if (Severity_Levels[parentIssueSeverityCurrent] < Severity_Levels[issueSeverityOriginal]):
                        audit[issue.number].append(1)
                    else:
                        audit[issue.number].append(0)

            else:
                audit[issue.number].extend([0,0,0])

        # Printing into csv

        output_path = OUTPUT_DIR+"/pe_checks/"
        output_file = output_path+"pe_issue_checks.csv"

        if not os.path.exists(output_path):
            os.makedirs(output_path)
        wr = csv.writer(open(output_file, 'w'), delimiter=',', quoting=csv.QUOTE_ALL)
        wr.writerow(CSV_HEADER)

        for issue in all_issues:
            assert(len(audit[issue.number])==(len(CSV_HEADER)-1))
            to_print = [issue.number]+audit[issue.number]
            wr.writerow(to_print)












