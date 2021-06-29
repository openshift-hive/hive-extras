# hive-extras

Hive-related things that don't belong in the [source repo](https://github.com/openshift/hive)
and aren't [SOPs](https://github.com/openshift/hive-sops).

## Resource Monitoring
The [monitoring subdirectory](monitoring) contains code that watches cloud resources, e.g. to make
sure we're not leaving things around that cost us money unnecessarily.

### AWS

The [monitoring/aws subdirectory](monitoring/aws) contains code that uses the
[AWS Lambda service](https://aws.amazon.com/lambda/) to monitor our
[Hive Team Cluster](https://github.com/openshift-hive/hive-team).
There are currently two setups:

- `periodicHiveLambdaFunction` monitors instance usage and emails a report daily at 6pm ET.
- `ciMonitorLambdaFunction` looks for leaked resources from CI jobs and emails a report iff any are found.
  We consider it a leak if any CI cluster (named with the prefix `hiveci-`) is more than 4h old.

<!-- TODO: More explanation might be appropriate. Which files relate to which functions, how to set up *policys, generally how things are plumbed. -->

#### Installation

**Prerequisites:**
- Ansible CLI, e.g. `sudo yum install ansible`
- Python3
- Some modules, maintained in [requirements.txt](monitoring/aws/requirements.txt).
  Install via `python3 -m pip install --user -r monitoring/aws/requirements.txt`
- Authentication to the Hive team's AWS account, e.g. via a credentials file or environment variables.

To install a playbook, you can simply execute its yaml file, e.g.:

```
./monitoring/aws/upload-ci-monitor-lambda.yaml
```

#### Live Testing

- [Log into the Hive team's AWS console](https://openshift-cluster-operator.signin.aws.amazon.com/console)
- Navigate to the Code tab for the lambda function you wish to test:
  - [periodicHiveLambdaFunction (daily running instance report)](https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions/periodicHiveLambdaFunction?tab=code)
  - [ciMonitorLambdaFunction (detects leaks from CI jobs)](https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions/ciMonitorLambdaFunction?tab=code)
- Create or load a Test configuration using the drop-down next to the orange "Test" button.
  The JSON payload will depend on the function you're running.
  (If testing, you may wish to configure the `"recipients"` list so the emails only come to you.)
- Punch the orange "Test" button.
