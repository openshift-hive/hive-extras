# VSphere utilities
- [`vmcdns.py`: View, Reserve, and Release DEVQE VMC DNS Entries](#vmcdnspy-view-reserve-and-release-devqe-vmc-dns-entries)
  - [One-Time Setup](#one-time-setup)
  - [Use It](#use-it)
    - [(Optional) Activate Virtual Environment](#optional-activate-virtual-environment)
    - [Point to the Right AWS Account](#point-to-the-right-aws-account)
    - [Show Reserved IPs](#show-reserved-ips)
    - [Show Available IPs in a Segment](#show-available-ips-in-a-segment)
    - [Generate an `install-config.yaml` Template (and Reserve IPs)](#generate-an-install-configyaml-template-and-reserve-ips)
    - [Profit](#profit)
    - [Release IPs](#release-ips)

## `vmcdns.py`: View, Reserve, and Release DEVQE VMC DNS Entries
The DEVQE environment has predefined network segments in which static IP addresses can be reserved for use with VSphere clusters.
This DNS management is done in the [openshift-vmware-cloud-ci AWS account](https://openshift-vmware-cloud-ci.signin.aws.amazon.com/console) (726924432237), for which you should have received credentials during [onboarding](https://docs.google.com/document/d/1cnzKMT-8TGcq5ox_AajGpT-VRwMuYTKIZI-fPNrR8Xg/edit#heading=h.bycjc9mvj2ia).

### One-Time Setup
- [Get Python 3](https://www.python.org/downloads/)
- (Optional) [Set up a virtual environment](https://docs.python.org/3/library/venv.html)
- Install requirements
  (...in your venv, if using)
  ```
  curl -O https://raw.githubusercontent.com/openshift-hive/hive-extras/master/vsphere/requirements.txt
  source /path/to/venv/bin/activate  # If using a venv
  python -mpip install -r requirements.txt
  ```
- Download the executable
  ```
  curl -O https://raw.githubusercontent.com/openshift-hive/hive-extras/master/vsphere/vmcdns.py
  chmod +x vmcdns.py
  mv vmcdns.py /somewhere/in/your/PATH
  ```

### Use It

#### (Optional) Activate Virtual Environment
```
$ source /path/to/venv/bin/activate
```

#### Point to the Right AWS Account
You can do this by setting `$AWS_PROFILE`; or {`$AWS_ACCESS_KEY_ID` and `$AWS_SECRET_ACCESS_KEY`}; etc.

#### Show Reserved IPs
The script knows about the [DEVQE network segments](https://docs.google.com/document/d/1cnzKMT-8TGcq5ox_AajGpT-VRwMuYTKIZI-fPNrR8Xg/edit#heading=h.pt8d46lus3jk).
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

#### Show Available IPs in a Segment
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

#### Generate an `install-config.yaml` Template (and Reserve IPs)
```
$ ./vmcdns.py install-config --network devqe-segment-222 --reserve efried-2254-413
Reserving IPs for API (192.168.222.5) and ingress (192.168.222.6)...

apiVersion: v1
baseDomain: vmc.devcluster.openshift.com
metadata:
  name: efried-2254-413
platform:
  vsphere:
    apiVIP: 192.168.222.5
    cluster: DEVQEcluster
    datacenter: DEVQEdatacenter
    defaultDatastore: vsanDatastore
    ingressVIP: 192.168.222.6
    network: devqe-segment-222
    username: YOUR_USERNAME_HERE
    password: YOUR_PASSWORD_HERE
    vCenter: vcenter.devqe.ibmc.devcluster.openshift.com
    # ?
    # resourcePool: /DEVQEdatacenter/host/DEVQEcluster/Resources/hive01
networking:
  machineNetwork:
  - cidr: 192.168.222.0/24
pullSecret: |
  YOUR_PULL_SECRET_HERE
sshKey: |
  YOUR_SSH_PUBLIC_KEY_HERE


Your IP addresses have been reserved in the AWS hosted zone!
```
**NOTE:** Omitting the `--reserved` argument will still generate a template with IPs in it, but will not reserve those IPs for you!

#### Profit

#### Release IPs
Once you have destroyed your cluster, don't forget to release the IPs you reserved above.
```
$ ./vmcdns.py release --cluster-name efried-2254-413 --api-vip 192.168.222.5 --ingress-vip 192.168.222.6
Releasing IPs for API (192.168.222.5) and ingress (192.168.222.6)...
```