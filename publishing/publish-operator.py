#!/usr/bin/env /usr/bin/python
#
# Script to publish a Hive operatorhub bundle (generated separately) to both the
# OpenShift OperatorHub repo (https://github.com/redhat-openshift-ecosystem/community-operators-prod)
# as well as the Kubernetes OperatorHub repo (https://github.com/k8s-operatorhub/community-operators)
#
# The script will clone a fresh copy of each repo in a temporary directory.
#
# Example:
#
# GITHUB_TOKEN="YOUR-GITHUB-TOKEN" ./publish-operator.py --new-version 1.1.13 --bundle-dir /path/to/bundle --github-user myusername --verbose --dry-run
#

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import yaml

# Hive dir within both:
# https://github.com/redhat-openshift-ecosystem/community-operators-prod
# https://github.com/k8s-operatorhub/community-operators
HIVE_SUB_DIR = 'operators/hive-operator'

SUBPROCESS_REDIRECT = subprocess.DEVNULL

def get_params():
    parser = argparse.ArgumentParser(description='Publish new hive version to operator hub.')
    parser.add_argument('--new-version', help='New hive release (eg 1.0.14)', required=True)
    parser.add_argument('--github-user', help="User's github username, if different than $USER", default=os.environ["USER"])
    parser.add_argument('--bundle-dir', help='Path to directory containing new operator bundle', required=True)
    parser.add_argument('--verbose', help='Show more details while running', action='store_true', default=False)
    parser.add_argument('--dry-run', help='Test run that skips pushing branches and submitting PRs', action='store_true', default=False)
    parser.add_argument('--update-channel', action='append', help='Update channel in OLM package to new version', required=True)

    args = parser.parse_args()

    if args.verbose:
        global SUBPROCESS_REDIRECT
        SUBPROCESS_REDIRECT = None
    return args

def main():
    params = get_params()

    with tempfile.TemporaryDirectory(prefix="operatorhub-push") as work_dir:

        # redhat-openshift-ecosystem/community-operators-prod
        open_pr(work_dir,
                "git@github.com:%s/community-operators-prod.git" % params.github_user,
                "git@github.com:redhat-openshift-ecosystem/community-operators-prod.git",
                params.github_user, params.bundle_dir, params.new_version, params.update_channel, params.dry_run)

        # k8s-operatorhub/community-operators
        open_pr(work_dir,
                "git@github.com:%s/community-operators.git" % params.github_user,
                "git@github.com:k8s-operatorhub/community-operators.git",
                params.github_user, params.bundle_dir, params.new_version, params.update_channel, params.dry_run)


def open_pr(work_dir, fork_repo, upstream_repo, gh_username, bundle_source_dir, new_version, update_channels, dry_run):

    dir_name = fork_repo.split('/')[1][:-4]

    dest_github_org = upstream_repo.split(':')[1].split('/')[0]
    dest_github_reponame = dir_name

    os.chdir(work_dir)

    print()
    print()
    print("Cloning %s" % fork_repo)
    cmd = ("git clone %s" % fork_repo).split()
    resp = subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT)
    if resp.returncode != 0:
        print("failed to clone repo")
        sys.exit(1)

    # get to the right place on the filesystem
    repo_full_path = os.path.join(work_dir, dir_name)
    print("Working in %s" % repo_full_path)
    os.chdir(repo_full_path)

    cmd = ("git remote add upstream %s" % upstream_repo).split()
    resp = subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT)
    if resp.returncode != 0:
        print("failed to add upstream remote")
        sys.exit(1)

    print("Fetching latest upstream")
    cmd = "git fetch upstream".split()
    resp = subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT)
    if resp.returncode != 0:
        print("failed to fetch upstream")
        sys.exit(1)

    # Starting branch
    print("Checkout latest upstream/main")
    cmd = "git checkout upstream/main".split()
    resp = subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT, stderr=SUBPROCESS_REDIRECT)
    if resp.returncode != 0:
        print("Failed to switch to upstream/main branch")
        sys.exit(1)

    branch_name = 'update-hive-{}'.format(new_version)
    pr_title = "Update Hive community operator to {}".format(new_version)
    print("Starting {}".format(pr_title))

    print("Create branch {}".format(branch_name))
    cmd = "git checkout -b {}".format(branch_name).split()
    resp = subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT, stderr=SUBPROCESS_REDIRECT)
    if resp.returncode != 0:
        print("Failed to checkout branch {}".format(branch_name))
        sys.exit(1)

    # copy bundle directory
    print("Copying bundle directory")
    bundle_files = os.path.join(bundle_source_dir, new_version)
    hive_dir = os.path.join(repo_full_path, HIVE_SUB_DIR, new_version)
    shutil.copytree(bundle_files, hive_dir)

    # update bundle manifest
    print("Updating bundle manfiest")
    bundle_manifests_file = os.path.join(repo_full_path, HIVE_SUB_DIR, "hive.package.yaml")
    bundle = {}
    with open(bundle_manifests_file, 'r') as a_file:
        bundle = yaml.load(a_file, Loader=yaml.SafeLoader)

    found = False
    for channel in bundle["channels"]:
        if channel["name"] in update_channels:
            found = True
            channel["currentCSV"] = "hive-operator.v{}".format(new_version)

    if not found:
        print("did not find a CSV channel to update")
        sys.exit(1)

    with open(bundle_manifests_file, 'w') as outfile:
        yaml.dump(bundle, outfile, default_flow_style=False)
    print("\nUpdated bundle package:\n\n")
    cmd = ("cat %s" % bundle_manifests_file).split()
    subprocess.run(cmd)
    print()

    # commit files
    print("Adding file")
    cmd = ("git add %s" % HIVE_SUB_DIR).split()
    subprocess.run(cmd)

    print("Commiting {}".format(pr_title))
    cmd = 'git commit --signoff '.split()
    cmd.append('--message="{}"'.format(pr_title))
    resp = subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT)
    if resp.returncode != 0:
        print("Failed to commit")
        sys.exit(1)
    print()

    if not dry_run:
        print("Pushing branch {}".format(branch_name))
        cmd = 'git push origin {} --force'.format(branch_name).split()
        resp = subprocess.run(cmd, stdout=SUBPROCESS_REDIRECT, stderr=SUBPROCESS_REDIRECT)
        if resp.returncode != 0:
            print("failed to push branch to origin")
            sys.exit(1)

        # open PR
        gh = importlib.import_module('github')
        client = gh.GitHubClient(dest_github_org, dest_github_reponame, "")

        from_branch = "{}:{}".format(gh_username, branch_name)
        to_branch = "main"

        resp = client.create_pr(from_branch, to_branch, pr_title)
        if resp.status_code != 201: #201 == Created
            print(resp.text)
            sys.exit(1)

        json_content = json.loads(resp.content.decode('utf-8'))
        print("PR opened: {}".format(json_content["html_url"]))

    else:
        print("Skipping branch push due to dry-run")
    print()

if __name__ == "__main__":
    main()
