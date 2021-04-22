#!/usr/bin/env /usr/bin/python
 
import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import yaml

GITHUB_CLIENT_USERNAME = "operator-framework"
GITHUB_CLIENT_REPONAME = "community-operators"

COMMUNITY_OPERATOR_MAIN_BRANCH = 'master'
COMMUNITY_OPERATOR_DIR = 'community-operators/hive-operator'
UPSTREAM_COMMUNITY_OPERATOR_DIR = 'upstream-community-operators/hive-operator'

SUBPROCESS_REDIRECT = subprocess.DEVNULL

def get_params():
    parser = argparse.ArgumentParser(description='Publish new hive version to operator hub.')
    parser.add_argument('--new-version', help='New hive release (eg 1.0.14)', required=True)
    parser.add_argument('--repo-dir', help='Path to root of repo to commit operator bundle to', required=True)
    parser.add_argument('--bundle-dir', help='Path to directory containing new operator bundle', required=True)
    parser.add_argument('--verbose', help='Show more details while running', action='store_true', default=False)
    
    args = parser.parse_args()

    repo_dir = args.repo_dir
    if repo_dir == None:
        repo_dir = os.getcwd()
    
    if args.verbose:
        global SUBPROCESS_REDIRECT
        SUBPROCESS_REDIRECT = None
    return args

def main():
    params = get_params()
    
    # get to the right place on the filesystem
    community_operator_repo_full_path = os.path.abspath(params.repo_dir)
    os.chdir(community_operator_repo_full_path)

    # get the local user's github username
    cmd = "git ls-remote --get-url origin".split()
    resp = subprocess.run(cmd, capture_output=True)
    personal_gh_user, _ = get_github_repo_data(resp.stdout.decode('utf-8'))

    print("Fetching latest upstream") 
    cmd = "git fetch upstream".split()
    resp = subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT)
    if resp.returncode != 0:
        print("failed to fetch upstream")
        sys.exit(1)

    print("Reset to upstream/master")
    cmd = "git reset upstream/master".split()
    resp = subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT)
    if resp.returncode != 0:
        print("Failed to set upstream/master")
        sys.exit(1)

    # community-operators
    branch_name = 'add-community-hive-{}'.format(params.new_version)
    pr_title = "Hive community operator {}".format(params.new_version)
    open_pr(pr_title, personal_gh_user, branch_name, community_operator_repo_full_path, params.bundle_dir, COMMUNITY_OPERATOR_DIR, params.new_version)

    # upstream-community-operators
    branch_name = 'add-upstream-community-hive-{}'.format(params.new_version)
    pr_title = "Hive upstream community operator {}".format(params.new_version)
    open_pr(pr_title, personal_gh_user, branch_name, community_operator_repo_full_path, params.bundle_dir, UPSTREAM_COMMUNITY_OPERATOR_DIR, params.new_version)


def open_pr(pr_title, gh_username, new_branch_name, repo_full_path, bundle_source_dir, bundle_target_dir_name, new_version):
    print("Starting {}".format(pr_title))

    # Starting branch
    cmd = "git checkout {}".format(COMMUNITY_OPERATOR_MAIN_BRANCH).split()
    resp = subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT, stderr=SUBPROCESS_REDIRECT)
    if resp.returncode != 0:
        print("Failed to switch to {} branch".format(COMMUNITY_OPERATOR_MAIN_BRANCH))
        sys.exit(1)

    print("Create branch {}".format(new_branch_name))
    cmd = "git checkout -b {}".format(new_branch_name).split()
    resp = subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT, stderr=SUBPROCESS_REDIRECT)
    if resp.returncode != 0:
        print("Faled to checkout branch {}".format(new_branch_name))
        sys.exit(1)

    # copy bundle directory
    bundle_files = os.path.join(bundle_source_dir, new_version)
    hive_dir = os.path.join(repo_full_path, bundle_target_dir_name, new_version)
    shutil.copytree(bundle_files, hive_dir)

    # update bundle manifest
    bundle_manifests_file = os.path.join(repo_full_path, bundle_target_dir_name, "hive.package.yaml")
    bundle = {}
    with open(bundle_manifests_file, 'r') as a_file:
        bundle = yaml.load(a_file, Loader=yaml.SafeLoader)

    found = False
    for channel in bundle["channels"]:
        if channel["name"] == "alpha":
            found = True
            channel["currentCSV"] = "hive-operator.v{}".format(new_version)

    if not found:
        print("did not find a CSV channel to update")
        sys.exit(1)

    with open(bundle_manifests_file, 'w') as outfile:
        yaml.dump(bundle, outfile, default_flow_style=False)

    # commit files
    cmd = "git add community-operators/hive-operator".split()
    subprocess.run(cmd)

    print("Commiting {}".format(pr_title))
    cmd = 'git commit --signoff '.split()
    cmd.append('--message="{}"'.format(pr_title))
    subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT)

    print("Pushing branch {}".format(new_branch_name))
    cmd = 'git push origin {} --force'.format(new_branch_name).split()
    resp = subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT, stderr=SUBPROCESS_REDIRECT)
    if resp.returncode != 0:
        print("failed to push branch to origin")
        sys.exit(1)

    # open PR
    gh = importlib.import_module('github')
    client = gh.GitHubClient(GITHUB_CLIENT_USERNAME, GITHUB_CLIENT_REPONAME, "")

    from_branch = "{}:{}".format(gh_username, new_branch_name)
    to_branch = COMMUNITY_OPERATOR_MAIN_BRANCH
    
    resp = client.create_pr(from_branch, to_branch, pr_title)
    if resp.status_code != 201: #201 == Created
        print(resp.text)
        sys.exit(1)

    json_content = json.loads(resp.content.decode('utf-8'))
    print("PR opened: {}".format(json_content["html_url"]))

# get_repo_data will take a git remote URL and decode
# the github username and reponame from the URL
def get_github_repo_data(repo_url):

    user = ""
    repo = ""

    if repo_url.startswith("http"):
        print("implement fetching username/reponame from http url")
        sys.exit(1)
    elif repo_url.startswith("git@"): # "git@github.com:USERNAME/REPONAME.git"
        m = re.search('.*:([-0-9a-zA-Z_]+)/([-0-9a-zA-Z_]+).git', repo_url)
        user = m.group(1)
        repo = m.group(2)
    else:
        print("don't know how to unpack repo_url {}".format(repo_url))
        sys.exit(1)
        
    return (user, repo)

if __name__ == "__main__":
    main()
