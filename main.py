from controllers import IssueController, OrganisationController, TeamProjectMergeStatusDetector
from controllers import AddressbookPRDetector, CreateFeedback, Week_6
from common.config import AppConfig
from connectors.github import GitHubConnector
import datetime
import parsers

import argparse, logging, sys

cfg = AppConfig()
ghc = GitHubConnector(cfg.get_api_key(), cfg.get_repo(), cfg.get_organisation())
issue_ctrl = IssueController(ghc)
org_ctrl = OrganisationController(ghc)
proj_detector = TeamProjectMergeStatusDetector(cfg)
addressbook_ctrl = AddressbookPRDetector(cfg)
create_feedback_ctrl = CreateFeedback(cfg)
week_6_ctrl = Week_6(cfg)

def test():
    """Tests sample APIs (to be removed later)"""

    #r = ghc.organisation.get_repo("main")
    # r = ghc.repo
    # # startdate = datetime.datetime(2018,1,27)
    # # enddate = datetime.datetime(2018,8,14)
    # #
    # # for PR in r.get_pulls(state="closed"):
    # #     print(PR.user, PR.closed_at, PR.is_merged())
    # for i in range(100) :
    #     ghc.create_issue(title='ThrottleTest ' + str(i),msg='DummyTesxt', assignee=None)

    repo = GitHubConnector(cfg.get_api_key(),  "CS2103JAN2018-W09-B2/main", "CS2103JAN2018-W09-B2").repo
    for pr in repo.get_pulls(state="all", sort="updated", direction="desc"):
        for commit in pr.get_commits():
            for file in commit.files:
                print(commit.author.login, file.filename, file.changes)
        print()
    print(repo.full_name)

def setup_logger():
    """Sets up the logger"""
    logging.basicConfig(filename='log.log',level=logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

def setup_argparse():
    """Sets up argparse"""
    parser = argparse.ArgumentParser(description='useful command line tools for GitHub')
    subparsers = parser.add_subparsers(dest='group', help='GitHub component in question')
    subparsers.required = True
    issue_ctrl.setup_argparse(subparsers)
    org_ctrl.setup_argparse(subparsers)
    proj_detector.setup_argparse(subparsers)
    addressbook_ctrl.setup_argparse(subparsers)
    create_feedback_ctrl.setup_argparse(subparsers)
    week_6_ctrl.setup_argparse(subparsers)

    return parser

if __name__ == '__main__':
    # test()
    # exit()

    setup_logger()
    logging.info('hubatch - GitHub CLI tools: Started!')
    parser = setup_argparse()
    args = parser.parse_args()
    args.func(args)
