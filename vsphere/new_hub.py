#!/usr/bin/env python

import argparse
import os
import re
import subprocess
import sys

import vmcdns
from netaddr import *


def debug(*a, **k):
    if ARGS.debug:
        print("DEBUG: ", *a, file=sys.stderr, **k)

def is_valid_ssh_file(filename):
    with open(filename, "r") as f:
        if "PRIVATE" in f.read():
            print("ERROR: {} is a private key file. Please use a public key file.".format(filename), file=sys.stderr)
            sys.exit(-1)
    return filename

def build_parser():
    parser = argparse.ArgumentParser(
    prog="new_hub.py",
    description="Provision new cluster on vsphere. "+
        "NOTE: Make sure $AWS_PROFILE points to your creds for the openshift-vmware-cloud-ci account.",
    )
    parser.add_argument("--debug", action="store_true", help="Print debug output.")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", help="Don't actually do anything.")

    subparsers = parser.add_subparsers(dest="subcommand")

    # create-cluster subcommand 
    create = subparsers.add_parser("create-cluster", help="Create a new cluster. NOTE: GOVC_USERNAME and GOVC_PASSWORD env variables must be set.")
    create.add_argument("cluster_name", type=str, metavar="CLUSTER_NAME", help="The name of the cluster to create.")
    # TODO: check that api_vip and ingress_vip are valid IPs
    create.add_argument("--api-vip", metavar="API_VIP", dest="api_vip", help="The optional IP address for api. NOTE: Script does not check whether this IP is already reserved in DNS")
    create.add_argument("--ingress-vip", metavar="INGRESS_VIP", dest="ingress_vip", help="The optional IP address for *.apps. NOTE: Script does not check whether this IP is already reserved in DNS")
    create.add_argument("--dir", metavar="DIR", default=os.getcwd(), help="The directory to save the install-config.yaml file to. Defaults to current working directory.")
    create.add_argument("--install-hive", dest="install_hive", action="store_true", help="Install Hive on the cluster. NOTE: Can only be run from hive directory." + 
                            "NOTE: Make sure $IMG points to the hive image you want to install.")
    create.add_argument("--pull-secret", required=True, metavar="PULL_SECRET_FILE", help="The pull secret file to use for the cluster.")
    create.add_argument("--ssh-key", required=True, type=is_valid_ssh_file, metavar="SSH_KEY_FILE", help="The ssh key file to use for the cluster. You may download and use the team key from the hive-team repo at https://github.com/openshift-hive/hive-team/tree/master/repo-creds ")

    network_kwargs = dict(choices=list(vmcdns.SEGMENTS_BY_NAME.keys()), help="The network segment to query.")
    mutexgrp = create.add_mutually_exclusive_group()
    mutexgrp.add_argument("--network", **network_kwargs)
    mutexgrp.add_argument("--disconnected", action="store_true", help="Use a disconnected segment (a public segment will be used by default).")
   
    # destroy-cluster subcommand
    destroy = subparsers.add_parser("cleanup-cluster", help="Destroy and existing cluster and release its IPs.")
    destroy.add_argument("cluster_name", type=str, metavar="CLUSTER_NAME", help="The name of the cluster to destroy.")
    destroy.add_argument("--dir", metavar="DIR", default=os.getcwd(), help="The assets directory laid down by the installation. Defaults to current working directory.")
    destroy.add_argument("--api-vip", required=True, help="The IP address to release for api.")
    destroy.add_argument("--ingress-vip", required=True, help="The IP address to release for *.apps.")

    return parser

def check_args():
    debug(ARGS)

    if not ARGS.subcommand:
        print("Subcommand required", file=sys.stderr)
        PARSER.print_help()
        sys.exit(-1)
    if ARGS.subcommand == "create-cluster":
        debug("Creating cluster {}".format("and installing hive" if ARGS.install_hive else ""))

        CREDS.username = os.environ.get("GOVC_USERNAME")
        if not CREDS.username:
            print("GOVC_USERNAME not set", file=sys.stderr)
            sys.exit(-1)
        CREDS.password = os.environ.get("GOVC_PASSWORD")
        if not CREDS.password:
            print("GOVC_PASSWORD not set", file=sys.stderr)
            sys.exit(-1)

        CREDS.set_pull_secret(ARGS.pull_secret)
        CREDS.set_ssh_key(ARGS.ssh_key)

        if ARGS.install_hive:
            if not os.environ.get("IMG"):
                print("IMG not set", file=sys.stderr)
                sys.exit(-1)

        if (ARGS.network or ARGS.disconnected) and (ARGS.api_vip or ARGS.ingress_vip):
            print("Cannot specify both --network/--disconnected and --api-vip/--ingress-vip", file=sys.stderr)
            sys.exit(-1)
        if not (ARGS.api_vip and ARGS.ingress_vip) and (ARGS.api_vip or ARGS.ingress_vip):
            print("Must specify both --api-vip and --ingress-vip", file=sys.stderr)
            sys.exit(-1)
    return ARGS

def ping_ip(ip):

    command = ["ping", "-c", "1", ip]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode == 0:
        print("Error: {} is already in use".format(ip), file=sys.stderr)
        sys.exit(-1)
    elif result.returncode == 1:
        debug("ip {} is available".format(ip))
        return ip
    else:
        print("Error: {}".format(result.stderr), file=sys.stderr)
        sys.exit(-1)

def check_vips(api_vip, ingress_vip):
    debug("Pinging api_vip: {}".format(api_vip))
    debug("api_vip {} is available".format(ping_ip(api_vip)))
    debug("Pinging ingress_vip: {}".format(ingress_vip))
    debug("ingress_vip {} is available".format(ping_ip(ingress_vip)))

    # FIXME: this is a hack to get the segment name, don't do this
    segname = None
    pattern = r'^(\d+\.\d+\.\d+)\.'
    match = re.search(pattern, api_vip)
    for _, segment in vmcdns.SEGMENTS_BY_NAME.items():
        if match.group(0) in str(segment.network):
            return [api_vip, ingress_vip], segname
    else:
        print("Error: could not find segment name for api_vip {}".format(api_vip), file=sys.stderr)
        sys.exit(-1)

def get_networks():
    if ARGS.network:
        return [ARGS.network]
    elif ARGS.disconnected:
        return [segname for segname in vmcdns.SEGMENTS_BY_NAME.keys() if "-disconnected" in segname]
    else:
        return [segname for segname in vmcdns.SEGMENTS_BY_NAME.keys() if "-disconnected" not in segname]
    
def save_install_config(ips, segname, cluster_name, creds):
    install_config = vmcdns.get_install_config(ips, segname, cluster_name, creds)
    # TODO check that this is a valid directory
    filename = "install-config.yaml"
    if ARGS.dir:
        filename = os.path.join(ARGS.dir, "install-config.yaml")
    with open(filename, "w") as f:
        f.write(install_config)

def create_cluster(dir):
    try:
        subprocess.run(["openshift-install", "create", "cluster", "--dir", dir, "--log-level=info"], check=True)
    except subprocess.CalledProcessError as e:
        print("ERROR: {}".format(e), file=sys.stderr)
        print("Run the cleanup-cluster subcommand to clean up the cluster", file=sys.stderr)
        sys.exit(-1)

def destroy_cluster(dir):
    try:
        subprocess.run(["openshift-install", "destroy", "cluster", "--dir", dir, "--log-level=info"], check=True)
    except subprocess.CalledProcessError as e:
        print("ERROR: {}".format(e), file=sys.stderr)
        sys.exit(-1)

def install_hive(dir):
    try:
        subprocess.run(["make", "deploy"], check=True)
    except subprocess.CalledProcessError as e:
        print("ERROR: {}".format(e), file=sys.stderr)
        sys.exit(-1)

if __name__ == "__main__":
    PARSER = build_parser()
    ARGS = PARSER.parse_args()
    vmcdns.ARGS = type('', (), dict(debug=ARGS.debug))
    CREDS = vmcdns.Creds()
    check_args()

    if ARGS.subcommand == "create-cluster":
        avail = []
        if ARGS.api_vip and ARGS.ingress_vip:
           avail, segname = check_vips(ARGS.api_vip, ARGS.ingress_vip)
        else:
            vmcdns.discover_reserved_ips()
            networks = get_networks()
            for name in networks:
                avail = list(vmcdns.SEGMENTS_BY_NAME[name].available())
                if len(avail) < 2:
                    debug("Skipping segment %s: it doesn't have two available IPs")
                    continue
                segname = name
                if not ARGS.dry_run:
                    debug("Reserving IPs: {}".format(avail[:2]))
                    vmcdns.reserve_ips(avail[:2], ARGS.cluster_name)
        save_install_config(avail[:2], segname, ARGS.cluster_name, CREDS)
        if ARGS.dry_run:
            print("\nThis is a dry-run. Your IPs are not reserved!", file=sys.stderr)
        else:
            print("\nYour IP addresses have been reserved in the AWS hosted zone!", file=sys.stderr)
            create_cluster(ARGS.dir)
            if ARGS.install_hive:
                os.environ['KUBECONFIG'] = os.path.join(ARGS.dir, "auth", "kubeconfig")
                install_hive(ARGS.dir)
        sys.exit(0)
    if ARGS.subcommand == "cleanup-cluster":
        debug("Destroying cluster {}".format(ARGS.cluster_name))
        destroy_cluster(ARGS.dir)
        debug("Releasing IPs {}".format([ARGS.api_vip, ARGS.ingress_vip]))
        vmcdns.release_ips(ARGS.api_vip, ARGS.ingress_vip, ARGS.cluster_name)
        debug("Cleanup completed successfully")
        sys.exit(0)