# VSphere utilities
- [One-Time Setup](#one-time-setup)
- [Per-Session Setup](#per-session-setup)
  - [Activate Virtual Environment (If Using)](#activate-virtual-environment-if-using)
  - [Set Environment Variables](#set-environment-variables)
    - [Point to the Right AWS Account](#point-to-the-right-aws-account)
    - [Set VCenter Credentials (`new_hub.py` only)](#set-vcenter-credentials-new_hubpy-only)
  - [Connect to Twingate (`new_hub.py` Only)](#connect-to-twingate-new_hubpy-only)
- [`vmcdns.py`: View, Reserve, and Release DEVQE VMC DNS Entries](#vmcdnspy-view-reserve-and-release-devqe-vmc-dns-entries)
  - [Show Reserved IPs](#show-reserved-ips)
  - [Show Available IPs in a Segment](#show-available-ips-in-a-segment)
  - [Generate an `install-config.yaml` Template (and Reserve IPs)](#generate-an-install-configyaml-template-and-reserve-ips)
    - [Profit](#profit)
    - [Release IPs](#release-ips)
- [`new_hub.py`: Provision a VSphere Cluster in DEVQE Without Hive](#new_hubpy-provision-a-vsphere-cluster-in-devqe-without-hive)
  - [Download `openshift-install`](#download-openshift-install)
  - [Create the Cluster](#create-the-cluster)
  - [Destroy the Cluster](#destroy-the-cluster)

[onboarding]: https://docs.google.com/document/d/1cnzKMT-8TGcq5ox_AajGpT-VRwMuYTKIZI-fPNrR8Xg/edit#heading=h.bycjc9mvj2ia
[onboarding-segments]: https://docs.google.com/document/d/1cnzKMT-8TGcq5ox_AajGpT-VRwMuYTKIZI-fPNrR8Xg/edit#heading=h.pt8d46lus3jk

## One-Time Setup
- [Get Python 3](https://www.python.org/downloads/)
- (Optional) [Set up a virtual environment](https://docs.python.org/3/library/venv.html)
- Install requirements
  (...in your venv, if using)
  ```
  $ curl -O https://raw.githubusercontent.com/openshift-hive/hive-extras/master/vsphere/requirements.txt
  $ source /path/to/venv/bin/activate  # If using a venv
  $ python -mpip install -r requirements.txt
  ```
- Download the executable(s)
  ```
  for f in vmcdns.py new_hub.py; do
    curl -O https://raw.githubusercontent.com/openshift-hive/hive-extras/master/vsphere/$f
    chmod +x $f
    # Optional; you can also just invoke them with a path
    mv $f /somewhere/in/your/PATH
  done
  ```
- (`new_hub.py` only) Obtain a [pull secret](https://console.redhat.com/openshift/install/vsphere/user-provisioned) if you don't already have one.
- Install VCenter certs obtained during [onboarding][onboarding] on your local system.
  The following assumes Linux (please submit a PR to add your platform):
  ```bash
  $ sudo cp ~/vmc-ca.crt /etc/pki/ca-trust/source/anchors
  $ sudo update-ca-trust
  ```

## Per-Session Setup
### Activate Virtual Environment (If Using)
```
$ source /path/to/venv/bin/activate
```

### Set Environment Variables

#### Point to the Right AWS Account
This is the AWS account that manages route53 DNS entries for instances in the DEVQE environment.
You should have received credentials as part of VSphere [onboarding][onboarding].

You configure these credentials in your environment by setting `$AWS_PROFILE`; or {`$AWS_ACCESS_KEY_ID` and `$AWS_SECRET_ACCESS_KEY`}; etc.
For example, if you have configured a keypair for an IAM user in your credentials file:
```bash
$ export AWS_PROFILE=vmcdns
```

Alternatively, if you are set up to generate temporary tokens via SSO as described [here](https://docs.google.com/document/d/1yziT4KU2BhreGP7r1c9LySoW_MseQ5dDqpp6Cm3-18M/edit?tab=t.0#heading=h.3l2zuamu1xd8):

```bash
kinit <krbid>@IPA.REDHAT.COM
source /path/to/venv/bin/activate
/path/to/aws-saml.py
# Choose 726924432237-poweruser
export AWS_PROFILE=saml
```

#### Set VCenter Credentials (`new_hub.py` only)
`new_hub.py` expects `GOVC_USERNAME` and `GOVC_PASSWORD` to be set in your environment.
You should have received these credentials as part of VSphere [onboarding][onboarding].

```bash
$ export GOVC_USERNAME=efried-hive@devqe.ibmc.devcluster.openshift.com
$ export GOVC_PASSWORD="Gobbledyg00k*in-here"
```

### Connect to Twingate (`new_hub.py` Only)
When using utilities that access the VCenter, you must be connected to its VPN.
```bash
$ twingate start
# ...do the authn thing
```

If "twingate" doesn't sound familiar to you, please consult the [onboarding doc][onboarding].

## `vmcdns.py`: View, Reserve, and Release DEVQE VMC DNS Entries
The DEVQE environment has predefined network segments in which static IP addresses can be reserved for use with VSphere clusters.
This DNS management is done in the [openshift-vmware-cloud-ci AWS account](https://openshift-vmware-cloud-ci.signin.aws.amazon.com/console) (726924432237), for which you should have received credentials during [onboarding][onboarding].

**Prerequisites:**
* [One-Time Setup](#one-time-setup)
* [Per-Session Setup](#per-session-setup) ([VPN](#connect-to-twingate-new_hubpy-only) is not necessary)

### Show Reserved IPs
The script knows about the [DEVQE network segments][onboarding-segments].
You can show reservations for all segments:
```
$ ./vmcdns.py reserved

devqe-segment-221:


devqe-segment-222:
192.168.222.3	api.hive01.vmc.devcluster.openshift.com.
192.168.222.4	\052.apps.hive01.vmc.devcluster.openshift.com.
192.168.222.20	api.jcallen222.vmc.devcluster.openshift.com.
192.168.222.21	\052.apps.jcallen222.vmc.devcluster.openshift.com.

devqe-segment-223:


devqe-segment-224:


devqe-segment-225:
192.168.225.3	api.jspeed.vmc.devcluster.openshift.com.
192.168.225.4	\052.apps.jspeed.vmc.devcluster.openshift.com.

devqe-segment-226:


devqe-segment-227:


devqe-segment-228:


devqe-segment-229-disconnected:


devqe-segment-230-disconnected:


devqe-segment-231-disconnected:


devqe-segment-232-disconnected:


devqe-segment-233-disconnected:


devqe-segment-234-disconnected:

```

...or for one segment of your choice:
```
$ ./vmcdns.py reserved --network devqe-segment-222
192.168.222.3	api.hive01.vmc.devcluster.openshift.com.
192.168.222.4	\052.apps.hive01.vmc.devcluster.openshift.com.
192.168.222.20	api.jcallen222.vmc.devcluster.openshift.com.
192.168.222.21	\052.apps.jcallen222.vmc.devcluster.openshift.com.
```

### Show Available IPs in a Segment
```
$ ./vmcdns.py available --network devqe-segment-222
192.168.222.5
192.168.222.6
192.168.222.7
192.168.222.8
192.168.222.9
192.168.222.10
192.168.222.11
192.168.222.12
192.168.222.13
192.168.222.14
192.168.222.15
192.168.222.16
192.168.222.17
192.168.222.18
192.168.222.19
192.168.222.22
192.168.222.23
192.168.222.24
192.168.222.25
192.168.222.26
192.168.222.27
192.168.222.28
192.168.222.29
192.168.222.30
192.168.222.31
192.168.222.32
192.168.222.33
192.168.222.34
192.168.222.35
192.168.222.36
192.168.222.37
192.168.222.38
192.168.222.39
192.168.222.40
192.168.222.41
192.168.222.42
192.168.222.43
192.168.222.44
192.168.222.45
192.168.222.46
192.168.222.47
192.168.222.48
192.168.222.49
```

### Generate an `install-config.yaml` Template (and Reserve IPs)
```
$ vmcdns.py install-config --network devqe-segment-222 --reserve efried-2254-413
Reserving IPs for API (192.168.222.5) and ingress (192.168.222.6)...
Need to reserve ['192.168.222.5', '192.168.222.6'] for efried-2254-413

apiVersion: v1
baseDomain: vmc.devcluster.openshift.com
metadata:
  name: efried-2254-413
platform:
  vsphere:
    apiVIPs:
    - 192.168.222.5
    ingressVIPs:
    - 192.168.222.6
    vcenters:
    - server: vcenter-2.devqe.ibmc.devcluster.openshift.com
      user: YOUR_USERNAME_HERE
      password: YOUR_PASSWORD_HERE
      datacenters:
      - DEVQEdatacenter-2
    failureDomains:
    - name: fd1
      server: vcenter-2.devqe.ibmc.devcluster.openshift.com
      topology:
        computeCluster: /DEVQEdatacenter-2/host/DEVQEcluster-2
        datacenter: DEVQEdatacenter-2
        datastore: /DEVQEdatacenter-2/datastore/vsanDatastore
        networks:
        - devqe-segment-222
      zone: us-east
      region: us-east-1a
networking:
  machineNetwork:
  - cidr: 192.168.222.0/24
pullSecret: |
  YOUR_PULL_SECRET_HERE
sshKey: |
  YOUR_SSH_PUBLIC_KEY_HERE


Your IP addresses have been reserved in the AWS hosted zone!
```
**NOTE:** Omitting the `--reserve` argument will still generate a template with IPs in it, but will not reserve those IPs for you!

#### Profit

#### Release IPs
Once you have destroyed your cluster, don't forget to release the IPs you reserved above.
```
$ ./vmcdns.py release --cluster-name efried-2254-413 --api-vip 192.168.222.5 --ingress-vip 192.168.222.6
Releasing IPs for API (192.168.222.5) and ingress (192.168.222.6)...
```

## `new_hub.py`: Provision a VSphere Cluster in DEVQE Without Hive
**As a hive dev/test enigneer, I want to use hive to provision a cluster in the DEVQE VCenter.**

To do so, the hive hub needs to be able to access the VCenter's network, which is behind a VPN.
Possible solutions include:
- Use a hub on a cluster in some public cloud, like the hive-team cluster in AWS. But this would entail some complex networking setup, likely involving RH IT, to enable that cluster to communicate through the VPN.
- Run the hub on my laptop, in a KIND or similar k8s cluster, while connected to the VPN. This would probably work. But maybe I can't or don't want to run a local k8s cluster; or my testing wants the hub to be running real OpenShift.
- Create the hub cluster in the same network as the VPN, which in practical terms means it needs to be provisioned in the DEVQE VCenter. But I can't use hive to do that (see above); I need to use `openshift-install` directly. That's what this script is for.

**Prerequisites:**
* [One-Time Setup](#one-time-setup)
* [Per-Session Setup](#per-session-setup) (including [VPN](#connect-to-twingate-new_hubpy-only))

### Download `openshift-install`
- Get the URI of the [release](https://quay.io/repository/openshift-release-dev/ocp-release?tab=tags) you wish to install, e.g. `quay.io/openshift-release-dev/ocp-release:4.17.40-x86_64`.
- Extract the installer binary:
  `oc adm release extract --command=openshift-install -a /path/to/your/pull-secret quay.io/openshift-release-dev/ocp-release:4.17.40-x86_64`
- Move the binary into your `$PATH`. This is necessary because `new_hub.py` invokes it pathless.

### Create the Cluster
- Please name your hub with your krbID or some other way we can track you down later.
- If you wish to install hive on your hub, run the command from your hive repo clone with your `$IMG` environment variable pointing to the hive image you wish to use.

Example:
```bash
$ export IMG=quay.io/openshift-hive/hive:c248a51ae1
$ cd ~/repos/hive
$ new_hub.py create-cluster --pull-secret /path/to/pull-secret --ssh-key /path/to/id_rsa.pub --install-hive efried-hive-hub
```

This will automatically reserve API and ingress IPs, generate an install-config.yaml, invoke `openshift-install` to provision your cluster, and run `make deploy` to install hive in it.

For additional options, including using already-reserved IPs, see the inline help:

```
$ new_hub.py create-cluster --help
```

### Destroy the Cluster
You must supply the IPs reserved for you in the previous step.
If you can't remember them, you can use [`vmcdns.py reserved`](#show-reserved-ips) to find them.
If something goes wrong and the command doesn't complete, you may need to use [`vmcdns.py release`](#release-ips) to release your IPs.

```
$ new_hub.py cleanup-cluster --api-vip 192.168.222.5 --ingress-vip 192.168.222.6 efried-hive-hub
```

See the help text for more options.

```
$ new_hub.py cleanup-cluster --help
```
