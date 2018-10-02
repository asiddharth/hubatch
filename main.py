from controllers import Week_7, Week_6, Week_3, Week_5, TADuties
from common.config import AppConfig
from connectors.github import GitHubConnector
from github import Github, GithubException
import datetime
import parsers

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
# general_ctrl = General(cfg)
track_ta = TADuties(cfg)

def test():
    """Tests sample APIs (to be removed later)"""


    # sha = "5cc6d8b2dcb21742917a00feed277c55c686c9f7"
    # gh = Github(cfg.get_api_key())
    # r = gh.get_repo("devamanyu/main")
    # print(r.get_git_commit(sha).author.email)
    # print(r)

    # exit()

    r = ghc.organisation.get_repo("main")
    print(r.full_name)

    for i in range(1) :
        print(ghc.create_issue(title='ThrottleTest ' + str(i),msg='DummyTesxt', assignee=None))

    # repo = Github(cfg.get_api_key()).get_repo("se-edu/addressbook-level1")
    # start_datetime=datetime.datetime.strptime("30/8/2017", '%d/%m/%Y')
    # end_datetime=datetime.datetime.strptime("2/9/2017", '%d/%m/%Y')
    # print(start_datetime, end_datetime)

    # for branch in repo.get_branches():
    #     print(branch.name)
    # exit()

    # for commit in repo.get_commits(sha = "add-sort", since=start_datetime, until=end_datetime):
    #     print(commit.commit.message)
    # exit()


    # for pr in repo.get_pulls(state="all", sort="updated", direction="desc"):
    #     for commit in pr.get_commits():
    #         for file in commit.files:
    #             print(commit.author.login, file.filename, file.changes)
    #     print()
    # print(repo.full_name)

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
    track_ta.setup_argparse(subparsers)

    return parser

if __name__ == '__main__':

    setup_logger()
    logging.info('hubatch - GitHub CLI tools: Started!')
    parser = setup_argparse()
    args = parser.parse_args()
    args.func(args)
