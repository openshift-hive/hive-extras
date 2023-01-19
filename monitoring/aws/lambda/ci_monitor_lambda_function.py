#!/usr/bin/env python3

import boto3
import datetime
import json
import io

NOW = datetime.datetime.utcnow()

# Our CI job is configured to use cluster names of the form:
# hiveci-$timestamp-$pull
# and the e2e-pool test creates an additional cluster named:
# cdcci-$timestamp-$pull
NAME_FILTER = dict(Name='tag:Name', Values=['hiveci-*', 'cdcci-*'])
# Where $timestamp is the number of seconds since the epoch, in hex; and
# $pull is the PR number, also in hex.
def parse_vpc(vpc):
    ret = dict()
    ret['id'] = vpc['VpcId']
    vpc_name = get_tag_value(vpc, key='Name')
    _, hex_stamp, hex_pr, _ = vpc_name.split('-', 3)
    ret['datetime'] = datetime.datetime.utcfromtimestamp(int(hex_stamp, 16))
    ret['age'] = NOW - ret['datetime']
    ret['pr'] = int(hex_pr, 16)
    ret['owned'] = get_owned_string(vpc)
    return ret


def get_owned_string(o):
    for tag in o.get('Tags', []):
        if tag['Value'] == 'owned':
            return f"{tag['Key']}=owned"
    return None


def get_tag_value(o, key=None):
    for tag in o.get('Tags', []):
        if tag['Key'] == key:
            return tag['Value']
    return None


def lambda_handler(event, context):

    print(event)
    debug = bool(event.get('debug'))
    vpcs = {}

    for region in event["regions"]:
        ec2client = boto3.client('ec2', region)

        try:
            response = ec2client.describe_vpcs(Filters=[NAME_FILTER])
        except Exception as e:
            vpcs[region] = e
        else:
            vpcs[region] = response['Vpcs']

    formatted, count = build_report_text(vpcs, debug=debug)
    print(f"Email body:\n{formatted}\n")

    # Skip the email if no leaks detected; unless debugging
    if count or debug:
        send_email(event["recipients"], event["fromemail"], formatted, event["emailregion"])

    return {
        'statusCode': 200,
        'body': json.dumps('Lambda complete!')
    }

def build_report_text(vpcs_by_region, debug=False):
    buf = io.StringIO()
    count = 0

    for region, vpcs in vpcs_by_region.items():
        if isinstance(vpcs, Exception):
            buf.write(f"Error fetching VPCs from region {region}: {vpcs}\n")
            continue

        if len(vpcs) == 0:
            continue

        buf.write("Region: {}\n".format(region))
        for vpc in vpcs:
            parsed = parse_vpc(vpc)
            if debug or parsed['age'] > datetime.timedelta(hours=4):
                count += 1
                # You'll need to be logged in to the right account for this to work
                buf.write(f"  https://console.aws.amazon.com/vpc/home?region={region}#VpcDetails:VpcId={parsed['id']}\n")
                buf.write(f"    Created: {parsed['datetime']}\n")
                # Let's make age a little prettier
                age = parsed['age'].total_seconds()
                h, r = divmod(age, 3600)
                m, r = divmod(r, 60)
                buf.write(f"    Age: {int(h)}h{int(m)}m\n")
                # NOTE: This won't dtrt for prow rehearsals :)
                buf.write(f"    PR: https://github.com/openshift/hive/pull/{parsed['pr']}\n")
                # You'll need to be logged into the right account for this to work
                buf.write(f"    Cleanup (if you're lucky): hiveutil aws-tag-deprovision {parsed['owned']}\n")

        buf.write("\n")
        
    return buf.getvalue(), count

def send_email(recipients, fromemail, email_body, region):
    sesclient = boto3.client('ses', region)

    response = sesclient.send_email(
        Source=fromemail,
        Destination={
            'ToAddresses': recipients,
        },
        Message={
            'Subject': {'Data': 'Hive CI leak report'},
            'Body': {'Text': {'Data': email_body}},
        },
    )

    print("Email response: {}".format(response))

def main():
    event = {"regions": ["us-east-1", "us-east-2"],
            "recipients": ["someone@example.com"],
            "fromemail": "return@example.com",
            "emailregion": "us-east-1",
            }
    result = lambda_handler(event, "")
    print(result)

if __name__ == "__main__":
    main()
