"""
Issue-related tasks
"""
from .common import BaseController
from github import Github, GithubObject, GithubException
from pathlib import Path
import parsers
import pickle
import time
import os
import re
import csv
import random
from collections import defaultdict

import logging, re, time


###############################################################
FROMREPO = "nusCS2113-AY1819S1/pe2-results"
FROMREPO_DUMMY = "DummyTA1/main"

FROMREPOORIGINAL = "nusCS2113-AY1819S1/pe-2"

GITHUB_ID_COLUMN_INDEX=2 # mapping details: github id
TEAM_ASSIGNED_COLUMN_INDEX=7 # mapping details: assigned team
Production = False
LINK = "https://github.com/nusCS2113-AY1819S1/forum/issues"
###############################################################

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


    def post_issue_checks(self, args):
        
        # Read audit csv
        audit = self.read_audit_details(args.audit)

        # Copy all issues
        all_issues = self.get_issues_from_repository()

        # Message
        message = message_template["pe-checks"]

        for issue in all_issues:

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












