#!/usr/bin/env python

import argparse
import boto3
import botocore
from netaddr import *
import sys


class Segment:
    def __init__(self, cidr, dhcpstart) -> None:
        self.network = IPNetwork(cidr)
        self.dhcpstart = IPAddress(dhcpstart)

    def available(self):
        """Generator for IP address strings for available (unreserved) addresses in this segment."""
        for ip in self:
            if ip not in RESERVED:
                yield ip

    def reserved_str(self):
        """Generator for 'IP\tDNSNAME' strings for reserved addresses in this segment."""
        for ip in self:
            if ip in RESERVED:
                yield f"{ip}\t{RESERVED[ip]}"

    def __iter__(self):
        for ip in iter_iprange(self.network.first+3, self.dhcpstart-1):
            yield str(ip)

    def __str__(self) -> str:
        return "\n".join(str(ip) for ip in self)


# Source: https://docs.google.com/document/d/1cnzKMT-8TGcq5ox_AajGpT-VRwMuYTKIZI-fPNrR8Xg/edit#heading=h.pt8d46lus3jk
SEGMENTS_BY_NAME = {
    "devqe-segment-221": Segment("192.168.221.0/24", "192.168.221.128"),
    "devqe-segment-222": Segment("192.168.222.0/24", "192.168.222.50"),
    "devqe-segment-223": Segment("192.168.223.0/24", "192.168.223.50"),
    "devqe-segment-224": Segment("192.168.224.0/24", "192.168.224.50"),
    "devqe-segment-225": Segment("192.168.225.0/24", "192.168.225.50"),
    "devqe-segment-226": Segment("192.168.226.0/24", "192.168.226.50"),
    "devqe-segment-227": Segment("192.168.227.0/24", "192.168.227.50"),
    "devqe-segment-228": Segment("192.168.228.0/24", "192.168.228.50"),
    "devqe-segment-229-disconnected": Segment("192.168.229.0/24", "192.168.229.128"),
    "devqe-segment-230-disconnected": Segment("192.168.230.0/24", "192.168.230.128"),
    "devqe-segment-231-disconnected": Segment("192.168.231.0/24", "192.168.231.128"),
    "devqe-segment-232-disconnected": Segment("192.168.232.0/24", "192.168.232.128"),
    "devqe-segment-233-disconnected": Segment("192.168.233.0/24", "192.168.233.128"),
    "devqe-segment-234-disconnected": Segment("192.168.234.0/24", "192.168.234.128"),
}


HOSTED_ZONE_ID = 'Z0355267XBPSF2ILEW5O'
VMC_BASE_DOMAIN = "vmc.devcluster.openshift.com"

# IPs that already have records associated with them
RESERVED = dict()

# Singleton AWS Route53 client
R53CLIENT = None


def change_json(action, route, base_name, ip):
    if action not in ("UPSERT", "DELETE"):
        raise ValueError(f"BUG: change_json got invalid action '{action}'.")
    if route == "API":
        prefix = "api"
    elif route == "INGRESS":
        prefix = "*.apps"
    else:
        raise ValueError(f"BUG: change_json got invalid route '{route}'.")
    return {
        "Action": action,
        "ResourceRecordSet": {
            "Name": f"{prefix}.{base_name}.{VMC_BASE_DOMAIN}.",
            "Type": "A",
            "TTL": 60,
            "ResourceRecords": [{
                "Value": ip
            }],
        },
    }


def debug(*a, **k):
    if ARGS.debug:
        print(*a, file=sys.stderr, **k)


def discover_reserved_ips():
    debug("Querying Hosted Zone %s" % HOSTED_ZONE_ID)
    r53client = get_route53_client()
    kw = {}
    while True:
        try:
            res = r53client.list_resource_record_sets(HostedZoneId=HOSTED_ZONE_ID, MaxItems="10", **kw)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "AccessDenied":
                print("Access denied! Do you need to set $AWS_PROFILE and/or $AWS_ACCESS_KEY_ID/$AWS_SECRET_ACCESS_KEY?", file=sys.stderr)
                sys.exit(1)
            raise
        for rset in res.get('ResourceRecordSets'):
            if rset.get('Type') != "A": continue
            recs = rset.get('ResourceRecords')
            if not recs: continue
            for rec in recs:
                val = rec.get("Value")
                if val:
                    RESERVED[val] = rset["Name"]
                    debug("Reserved: %s" % val)
        if not res['IsTruncated']:
            break
        kw['StartRecordName'] = res['NextRecordName']
        kw['StartRecordType'] = res['NextRecordType']


def get_route53_client():
    global R53CLIENT
    if R53CLIENT is None:
        R53CLIENT = boto3.client("route53")
    return R53CLIENT


def print_install_config(vips, segname):
    cluster_name = ARGS.reserve or "YOUR_NAME_HERE"
    print(f'''
apiVersion: v1
baseDomain: {VMC_BASE_DOMAIN}
metadata:
  name: {cluster_name}
platform:
  vsphere:
    apiVIP: {vips[0]}
    cluster: DEVQEcluster
    datacenter: DEVQEdatacenter
    defaultDatastore: vsanDatastore
    ingressVIP: {vips[1]}
    network: {segname}
    username: YOUR_USERNAME_HERE
    password: YOUR_PASSWORD_HERE
    vCenter: vcenter.devqe.ibmc.devcluster.openshift.com
    # ?
    # resourcePool: /DEVQEdatacenter/host/DEVQEcluster/Resources/hive01
networking:
  machineNetwork:
  - cidr: {SEGMENTS_BY_NAME[segname].network}
pullSecret: |
  YOUR_PULL_SECRET_HERE
sshKey: |
  YOUR_SSH_PUBLIC_KEY_HERE
''')


def release_ips():
    print(f"Releasing IPs for API ({ARGS.api_vip}) and ingress ({ARGS.ingress_vip})...", file=sys.stderr)
    r53client = get_route53_client()
    r53client.change_resource_record_sets(
        HostedZoneId=HOSTED_ZONE_ID,
        ChangeBatch={
        "Comment": f"DELETE DNS records for cluster '{ARGS.cluster_name}' in domain '{VMC_BASE_DOMAIN}'.",
        "Changes": [
            change_json("DELETE", "API", ARGS.cluster_name, ARGS.api_vip),
            change_json("DELETE", "INGRESS", ARGS.cluster_name, ARGS.ingress_vip),
        ],
    })


def reserve_ips(two_ips):
    print(f"Reserving IPs for API ({two_ips[0]}) and ingress ({two_ips[1]})...", file=sys.stderr)
    r53client = get_route53_client()
    r53client.change_resource_record_sets(
        HostedZoneId=HOSTED_ZONE_ID,
        ChangeBatch={
        "Comment": f"UPSERT DNS records for cluster '{ARGS.reserve}' in domain '{VMC_BASE_DOMAIN}'.",
        "Changes": [
            change_json("UPSERT", "API", ARGS.reserve, two_ips[0]),
            change_json("UPSERT", "INGRESS", ARGS.reserve, two_ips[1]),
        ],
    })


PARSER = argparse.ArgumentParser(
    prog="vmcdns.py",
    description="Query IPs in the AWS Route53 hosted zone for the DEVQE VMC. "+
        "NOTE: Make sure $AWS_PROFILE points to your creds for that account.",
)
PARSER.add_argument("--debug", action="store_true", help="Print debug output.")

subparsers = PARSER.add_subparsers(dest="subcommand")

network_arg = "--network"
network_kwargs = dict(choices=list(SEGMENTS_BY_NAME.keys()), help="The network segment to query.")

parser_available = subparsers.add_parser("available", help="List (N) available IP addresses in a network segment.")
parser_available.add_argument(network_arg, **network_kwargs, required=True)
parser_available.add_argument("--count", metavar="N", type=int, help="Limit the output to N results.")

parser_reserved = subparsers.add_parser("reserved", help="List reserved IP addresses (in a network segment).")
parser_reserved.add_argument(network_arg, **network_kwargs)

parser_installconfig = subparsers.add_parser("install-config", help="Generate networky chunks of install-config.yaml, and optionally reserve IPs.")
mutexgrp = parser_installconfig.add_mutually_exclusive_group()
mutexgrp.add_argument(network_arg, **network_kwargs)
mutexgrp.add_argument("--disconnected", action="store_true", help="Use a disconnected segment (a public segment will be used by default).")
parser_installconfig.add_argument("--reserve", metavar="CLUSTER_NAME", help=f"Automatically reserve the discovered IPs for the named cluster in base domain {VMC_BASE_DOMAIN}.")

parser_release = subparsers.add_parser("release", help="Release IP addresses.")
parser_release.add_argument("--api-vip", required=True, help="The IP address for api.")
parser_release.add_argument("--ingress-vip", required=True, help="The IP address for *.apps.")
parser_release.add_argument("--cluster-name", required=True, help=f"Base name of the cluster currently owning the IPs (in domain '{VMC_BASE_DOMAIN}').")


if __name__ == "__main__":
    ARGS = PARSER.parse_args()
    if not ARGS.subcommand:
        print("Subcommand required. Use --help for usage.", file=sys.stderr)
        sys.exit(-1)

    if ARGS.subcommand != "release":
        discover_reserved_ips()

    if ARGS.subcommand == "available":
        iteravail = SEGMENTS_BY_NAME[ARGS.network].available()
        if ARGS.count:
            # TODO: make use of the generator rather than constructing the whole list
            print("\n".join(list(iteravail)[:ARGS.count]))
        else:
            print("\n".join(iteravail))
    elif ARGS.subcommand == "reserved":
        if ARGS.network:
            print("\n".join(SEGMENTS_BY_NAME[ARGS.network].reserved_str()))
        else:
            for name, segment in SEGMENTS_BY_NAME.items():
                print("\n%s:" % name)
                print("\n".join(segment.reserved_str()))
    elif ARGS.subcommand == "install-config":
        if ARGS.network:
            networks = [ARGS.network]
        elif ARGS.disconnected:
            networks = [segname for segname in SEGMENTS_BY_NAME.keys() if "-disconnected" in segname]
        else:
            networks = [segname for segname in SEGMENTS_BY_NAME.keys() if "-disconnected" not in segname]
        for segname in networks:
            avail = list(SEGMENTS_BY_NAME[segname].available())
            if len(avail) < 2:
                debug("Skipping segment %s: it doesn't have two available IPs")
                continue
            if ARGS.reserve:
                reserve_ips(avail[:2])
            print_install_config(avail[:2], segname)
            if ARGS.reserve:
                print("\nYour IP addresses have been reserved in the AWS hosted zone!", file=sys.stderr)
            else:
                print("\nYour IPs are not reserved! You may wish to run this command again with '--reserve your-cluster-name'", file=sys.stderr)
            sys.exit(0)
        print("Could not find any networks with two available IPs!", file=sys.stderr)
    elif ARGS.subcommand == "release":
        release_ips()
