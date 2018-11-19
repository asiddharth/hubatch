from controllers import Week_7, Week_6, Week_3, Week_5, Week_8, Week_9, Week_10, Week_11, Week_12, TADuties
from controllers import OrganisationController, IssueController, PeProcessing
from common.config import AppConfig
from connectors.github import GitHubConnector
from github import Github, GithubException
import datetime
import parsers
import time

import argparse, logging, sys

cfg = AppConfig()
ghc = GitHubConnector(cfg.get_api_key(), cfg.get_repo(), cfg.get_organisation())
# issue_ctrl = IssueController(ghc)
# org_ctrl = OrganisationController(ghc)
# proj_detector = TeamProjectMergeStatusDetector(cfg)
# addressbook_ctrl = AddressbookPRDetector(cfg)
# create_feedback_ctrl = CreateFeedback(cfg)
week_6_ctrl = Week_6(cfg)
week_3_ctrl = Week_3(cfg)
week_5_ctrl = Week_5(cfg)
week_7_ctrl = Week_7(cfg)
week_8_ctrl = Week_8(cfg)
week_9_ctrl = Week_9(cfg)
week_10_ctrl = Week_10(cfg)
week_11_ctrl = Week_11(cfg)
week_12_ctrl = Week_12(cfg)
pe_processing_ctrl = PeProcessing(ghc, cfg)
org_ctrl = OrganisationController(ghc, cfg)
issue_ctrl = IssueController(ghc, cfg)
track_ta = TADuties(cfg)

def test():
    """Tests sample APIs (to be removed later)"""


    # sha = "5cc6d8b2dcb21742917a00feed277c55c686c9f7"
    # gh = Github(cfg.get_api_key())
    # r = gh.get_repo("devamanyu/main")
    # print(r.get_git_commit(sha).author.email)
    # print(r)

    # exit()

    gh = Github(cfg.get_api_key())
    print(gh.get_rate_limit())

    for i in range(1) :
        print(i, ghc.create_issue(title='ThrottleTest ' + str(i*1000),msg='DummyText', assignee=None, repo="DummyTA1/main"))
        time.sleep(2)


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
    # issue_ctrl.setup_argparse(subparsers)
    # org_ctrl.setup_argparse(subparsers)
    # proj_detector.setup_argparse(subparsers)
    # addressbook_ctrl.setup_argparse(subparsers)
    # create_feedback_ctrl.setup_argparse(subparsers)
    week_6_ctrl.setup_argparse(subparsers)
    week_3_ctrl.setup_argparse(subparsers)
    week_5_ctrl.setup_argparse(subparsers)
    week_7_ctrl.setup_argparse(subparsers)
    week_8_ctrl.setup_argparse(subparsers)
    week_9_ctrl.setup_argparse(subparsers)
    week_10_ctrl.setup_argparse(subparsers)
    week_11_ctrl.setup_argparse(subparsers)
    week_12_ctrl.setup_argparse(subparsers)
    org_ctrl.setup_argparse(subparsers)
    issue_ctrl.setup_argparse(subparsers)
    track_ta.setup_argparse(subparsers)
    pe_processing_ctrl.setup_argparse(subparsers)

    return parser

if __name__ == '__main__':
    setup_logger()
    logging.info('hubatch - GitHub CLI tools: Started!')
    parser = setup_argparse()
    args = parser.parse_args()
    args.func(args)
