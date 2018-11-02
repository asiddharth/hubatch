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

import logging, re, time


###############################################################
FROMREPO = "nusCS2113-AY1819S1/pe-1"
TOREPO_PREFIX = "cs2113-AY1819S1-{}/main"
GITHUB_ID_COLUMN_INDEX=1 # mapping details: github id
TEAM_ASSIGNED_COLUMN_INDEX=4 # mapping details: assigned team
Production = True
###############################################################


REF_TEMPLATE = '\n\n<hr>\n\n**Reported by:** @{}\n**Severity:** {}\n\n<sub>[original: {}#{}]</sub>'
OUTPUT_PATH = "./output/PE-1/"
PE_FILE = "pe_1.p"
DUMMY = "dummy"
DUMMY_TOREPO = "DummyTA1/main"


class IssueController(BaseController):
    def __init__(self, ghc, cfg):
        self.ghc = ghc
        self.cfg = cfg
        self.gh = Github(self.cfg.get_api_key())

    def setup_argparse(self, subparsers):
        """
        Sets up the subparser for issue blaster
        """
        parser = subparsers.add_parser('issues', help='GitHub issue management tools')
        issue_subparsers = parser.add_subparsers(help='name of tool to execute')
        self.setup_blast_args(issue_subparsers)
        self.setup_copy_args(issue_subparsers)

    def setup_blast_args(self, subparsers):
        parser = subparsers.add_parser('blast', help='mass-create same issue for a list of GitHub users')
        parser.add_argument('csv', metavar='csv', type=str,
                            help='filename of the CSV containing a list of GitHub usernames')
        parser.add_argument('msg', metavar='markdown', type=str,
                            help='filename of file containing Markdown')
        parser.add_argument('title', metavar='title', type=str,
                            help='title for GitHub issue')
        parser.add_argument('-s', '--start-from', metavar='username', type=str,
                            help='start adding from a particular user (inclusive) in the CSV')
        parser.set_defaults(func=self.blast_command)

    def setup_copy_args(self, subparsers):
        parser = subparsers.add_parser('copy', help='copies issues from one repository to another')
        # parser.add_argument('fromrepo', metavar='from', type=str,
        #                     help='repository from which we should copy')
        # parser.add_argument('torepo', metavar='to', type=str,
        #                     help='repository to which we should copy to')
        parser.add_argument('-m', '--mapping', metavar='csv', type=str,
                            help='filename of CSV containing the title tag mapping')
        parser.set_defaults(func=self.copy_command)

    def blast_command(self, args):
        logging.debug('Issue title: %s', args.title)
        logging.debug('CSV file: %s and MD file: %s', args.csv, args.msg)

        if parsers.common.are_files_readable(args.csv, args.msg):
            self.blast_issues(args.csv, args.title, args.msg, args.start_from)
        else:
            sys.exit(1)

    def copy_command(self, args):
        # logging.debug('Copying from %s to %s', args.fromrepo, args.torepo)

        if parsers.common.are_files_readable(args.mapping):
            self.copy_issues(args.mapping)
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
            repo = self.gh.get_repo(FROMREPO)
            return repo.get_issues(state = "open", direction='asc')
        except GithubException as e:
            GitHubConnector.log_exception(e.data)
            return []

    def copy_issues(self, mapping_file):
        '''
        Copies issues from one repository to another
        '''

        # Load student mapping
        mapping_dict = self.extract_mapping_info(mapping_file)

        # Copy all issues
        if not os.path.exists(OUTPUT_PATH):
            os.makedirs(OUTPUT_PATH)
        my_file = Path("./temp.p")

        if not my_file.is_file():
            from_repo_issues = self.get_issues_from_repository()
            issues = []
            for issue in from_repo_issues:
                issues.append(issue)
            pickle.dump(issues, open("./temp.p", "wb"))
            pickle.dump(issues, open(OUTPUT_PATH+PE_FILE, "wb"))
            from_repo_issues = issues
        else:
            from_repo_issues = pickle.load(open("./temp.p", "rb"))


        print("Remaining no. of issues to copy: ", len(from_repo_issues))
        completed = None
        for idx, issue in enumerate(from_repo_issues):
            try:
                from_student = issue.user.login.lower()

                if len(issue.labels)==0:
                    LABEL = "Not Specified"
                else:
                    LABEL = "`{}`".format(issue.labels[0].name.split(".")[-1])

                TOREPO = TOREPO_PREFIX.format(mapping_dict[from_student])

                if Production:
                    print(TOREPO)
                    new_body = issue.body + REF_TEMPLATE.format(from_student, LABEL, FROMREPO, issue.number)
                    is_transferred = self.ghc.create_issue(title=issue.title,msg=new_body, assignee=None, repo=TOREPO)
                else:
                    new_body = issue.body + REF_TEMPLATE.format(DUMMY, LABEL, DUMMY, issue.number)
                    is_transferred = self.ghc.create_issue(title=issue.title,msg=new_body, assignee=None, repo=DUMMY_TOREPO)

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

    def blast_issues(self, csv_file, title, msg_file, start_from):
        """
        Creates a unique issue with identical content for
        every GitHub user in a specified CSV file
        """
        user_tag_list = parsers.csvparser.get_rows_as_list(csv_file)
        user_list = [x[0] for x in user_tag_list]
        message = parsers.common.get_contents(msg_file)

        if start_from and start_from in user_list:
            user_tag_list = user_tag_list[user_list.index(start_from):]

        failed_users = []

        quota = self.ghc.get_remaining_quota()
        num_issues = min(quota, len(user_tag_list))

        if quota < len(user_tag_list):
            num_issues = quota
            print('Insufficient quota! Run again (when quota resets) from', user_list[quota], 'user onwards!')
            logging.warn('Insufficient API quota!')
            logging.warn('Creating issues for users up till: %s (Next user: %s)', user_tag_list[quota - 1][0],  user_tag_list[quota][0])

        logging.info('Creating issues for %d user(s)', num_issues)

        for (user, user_title, *labels) in user_tag_list[:num_issues]:
            final_title = title.format(user_title)
            is_created = self.ghc.create_issue(final_title, message, user, labels)
            if not is_created:
                logging.error('Unable to create issue for user: %s', user)
                failed_users.append(user)
            time.sleep(2) # ensures app is within abuse rate limit

        num_issues = len(user_tag_list) - len(failed_users)

        logging.info('Blasting completed! %d issues created!', num_issues)

        if len(failed_users) > 0:
            logging.warn('Unable to create issue for users: %s', failed_users)