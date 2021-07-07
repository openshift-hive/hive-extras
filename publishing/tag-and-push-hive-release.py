#!/usr/bin/env /usr/bin/python
 
import argparse
import importlib
import json
import os
import subprocess

GITHUB_CLIENT_USERNAME = "openshift"
GITHUB_CLIENT_REPONAME = "hive"

def get_params():
    parser = argparse.ArgumentParser(description='Publish hive versions.')
    parser.add_argument('--new-version', help='New hive release (eg 1.0.14)', required=True)
    parser.add_argument('--new-commit-hash', help='Git commit ID associated with new version', required=True)
    parser.add_argument('--repo-dir', help='Path to root of repo to checkout/build images from', required=True)
    parser.add_argument('--registry-auth-file', help='Path to registry auth file (optional)')
    
    args = parser.parse_args()

    repo_dir = args.repo_dir
    if repo_dir == None:
        repo_dir = os.getcwd()
    
    return args

def build_image(repo_dir, registry_auth_file, tag):
    prev_dir = os.getcwd()
    os.chdir(repo_dir)

    try:
        # sync up git repo with remote
        cmd = "git fetch upstream".split()
        subprocess.run(cmd)
        cmd = "git fetch upstream --tags".split()
        subprocess.run(cmd)

        # checkout tag/commit
        cmd = 'git checkout {}'.format(tag).split()
        subprocess.run(cmd)

        container_name = 'quay.io/openshift-hive/hive:{}'.format(tag)

        # build/push the thing
        print("Building container")
        cmd = 'buildah bud --tag {} -f ./Dockerfile'.format(container_name).split()
        subprocess.run(cmd)

        print("Pushing container")
        cmd = 'buildah push '
        if registry_auth_file != None:
            cmd = cmd + ' --authfile={} '.format(registry_auth_file)
        cmd = cmd + ' {}'.format(container_name)
        subprocess.run(cmd.split())
    finally:
        os.chdir(prev_dir)

def main():
    params = get_params()

    gh = importlib.import_module('github')
    client = gh.GitHubClient(GITHUB_CLIENT_USERNAME, GITHUB_CLIENT_REPONAME, "")

    # A tag is a combination of a a tag plus a reference
    tag = 'v{}'.format(params.new_version)
    tag_msg = 'hive {}'.format(params.new_version)

    resp = client.create_annotated_tag(tag, tag_msg, params.new_commit_hash)
    if not resp.ok:
        print("Failed to tag: " + resp.text)
        exit(1)

    tag_sha = resp.json()["sha"]
    # ref format for tags is 'refs/tags/<tag-name>'
    tag_ref = 'refs/tags/{}'.format(tag)

    resp = client.create_reference(tag_ref, tag_sha)
    # Errors with "Reference already exists" if re-run with same version/hash
    if not resp.ok and json.loads(resp.text).get("message") != "Reference already exists":
        print("Failed to create tag reference: " + resp.text)
        exit(1)

    print("Created tag " + tag)

    build_image(params.repo_dir, params.registry_auth_file, tag)

if __name__ == "__main__":
    main()