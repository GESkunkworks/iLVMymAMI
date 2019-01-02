# vswitch

Switches a volume from one instance to another.

Helpful for debugging issues with creating bootable
volumes. 

Update the profile_name for your creds and update
instances and volid's dictionaries with your
instances and volume id's and then run with:

```
python vswitch.py
```

It will ask you which volume you want to move, what
the current source instance is, and what the desired
target instance is.

First it stops the source instance, detaches the volume
then it attaches the volume to the other instance and starts it.

Sample Run:
```
GC02RQ08ZG8WPE:volswitcher russellendicott$ python vswitch.py
1 : vol-02ecd9890707de650 (cheatroot)
2 : vol-048a760f6772d161a (canvas-simple)
Which volume would you like to move? (Enter a number) 2
1 : i-037d67f4c14a026b5 (c1)
2 : i-078531f8bda92e4f8 (d1)
3 : i-08c16eb847a489fe0 (d2)
4 : i-05cda464e5779ab51 (cheat)
What is the source instance that vol-048a760f6772d161a is currently attached to? (Enter a number) 3
What is the destination instance that you wish to attach vol-048a760f6772d161a to? (Enter a number) 1
Source instance: i-08c16eb847a489fe0
Destination instance: i-037d67f4c14a026b5
Polling 1 of 200
    Getting status of source instance: i-08c16eb847a489fe0
    State = stopped
Polling 1 of 200
    Getting status of source instance: i-037d67f4c14a026b5
    State = stopped
{'ResponseMetadata': {'RetryAttempts': 0, 'HTTPStatusCode': 200, 'RequestId': '8dcd8dbf-7f70-4dab-a9c5-6e7069998866', 'HTTPHeaders': {'date': 'Tue, 01 Jan 2019 15:16:56 GMT', 'content-length': '410', 'content-type': 'text/xml;charset=UTF-8', 'server': 'AmazonEC2'}}, u'AttachTime': datetime.datetime(2019, 1, 1, 15, 16, 56, 543000, tzinfo=tzutc()), u'InstanceId': 'i-037d67f4c14a026b5', u'VolumeId': 'vol-048a760f6772d161a', u'State': 'attaching', u'Device': '/dev/sdf'}
GC02RQ08ZG8WPE:volswitcher russellendicott$
```
