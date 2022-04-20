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
  - Your AWS user must be a member of the `lambda-admin` group, or have equivalent permissions.

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
  The JSON payload might vary depending on the function you're running.
  However, at the time of this writing, both jobs take the same configuration.
  Here is a sample (configure the `"recipients"` list so the emails only come to you):
  ```json
  {
    "regions": [
      "us-east-1",
      "us-east-2"
    ],
    "recipients": [
      "me@redhat.com"
    ],
    "fromemail": "openshift-hive-team@redhat.com",
    "emailregion": "us-east-1"
  }
  ```
- Punch the orange "Test" button.

#### Debugging

It's not intuitive (at least to me) to find the various pieces of these jobs and schedules in the AWS console.
Hopefully this helps.
First, [log into the Hive team's AWS console](https://openshift-cluster-operator.signin.aws.amazon.com/console).
Then these links should work:

|  | Running Instances | CI Monitor | Notes |
|-|-|-|-|
| **job code** | [link](https://us-east-1.console.aws.amazon.com/lambda/home?region=us-east-1#/functions/periodicHiveLambdaFunction?tab=code) | [link](https://us-east-1.console.aws.amazon.com/lambda/home?region=us-east-1#/functions/ciMonitorLambdaFunction?tab=code) | This should match the respective python script in [monitoring/aws/lambda/](monitoring/aws/lambda/) |
| **test pane** | [link](https://us-east-1.console.aws.amazon.com/lambda/home?region=us-east-1#/functions/periodicHiveLambdaFunction?tab=testing) | [link](https://us-east-1.console.aws.amazon.com/lambda/home?region=us-east-1#/functions/ciMonitorLambdaFunction?tab=testing) | See [above](#live-testing) for how to use this |
| **schedule** | [link](https://us-east-1.console.aws.amazon.com/events/home?region=us-east-1#/eventbus/default/rules/PeriodicHiveLambdaSchedule) | [link](https://us-east-1.console.aws.amazon.com/events/home?region=us-east-1#/eventbus/default/rules/ciMonitorLambdaSchedule) | Use the "Event schedule" tab to see the cron spec and upcoming runs<br>Use the "Targets" tab and click `Constant` under the `Input` column to see the current configuration<br>**Note:** We've had problems before when a second "Target" with no "Constant" configuration got mysteriously created. Deleting the schedule and rerunning the ansible uploader resolved it. |
| **logs** | [link](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws$252Flambda$252FperiodicHiveLambdaFunction) | [link](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws$252Flambda$252FciMonitorLambdaFunction) | |
