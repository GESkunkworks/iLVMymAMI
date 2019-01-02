#!/usr/bin/env python
'''
Creates an instance with an additional volume and userdata 
script passed in from config. It's assumed that the userdata
will prepare the additional volume as a bootable volume and
then stop the instance and snapshot/register the additional 
volume as an AMI with the information passed in via the config
file. 

See sample-config.yml for detailed documentation about config
options. 

Usage:
    python ilvmymami.py <config-file>

Example: python ilvmymami.py config-sample.yml


'''
import boto3
import json
import time
import yaml
import sys

class BaseClass:
    """
    Boilerplate config object class. Contains
    common methods such as debug dumpself and
    generic parsers. Designed to be inherited
    by other classes with more specific
    purpose.
    """
    def dumpself(self):
        """
        Loops through attributes of self 
        and returns a formatted message string
        listing all attributes and their values.
        """
        fmt = '\t{0:25}{1}\n'
        msg = ''
        for attr in dir(self):
            if (
                    '__' not in attr and
                    'instancemethod' not in str(type(getattr(self, attr)))):
                msg += (fmt.format(attr, getattr(self, attr)))
        return msg
    def parse_config(self, config):
        """
        Loops through provided config dictionary
        and sets properties dynamically on self. 
        If a property that has "tags" in the name
        is encountered it runs a specific tag
        parser function to conver the tags to 
        AWS format.
        """
        for prop,val in config.iteritems():
            if "tags" in prop:
		self.parse_tags(prop, val)
            else:
                setattr(self, prop, val)
    def parse_tags(self, tags_prop_name, list_of_tag_dict):
	"""
	Takes a list of tags in the format:
	  [{"key": "val"},{"key": "val"}]
        and builds a tags prop on self in 
        aws tags format (e.g.,
          [
	    {"Key": "key","Value":"val"} 
	    {"Key": "key","Value":"val"}
	  ]
	"""
	temp_tags = []
	for tag in list_of_tag_dict:
	    k = tag.keys()[0]
	    t = {
		"Key": k,
		"Value": tag[k] 
	    }
	    temp_tags.append(t)
	setattr(self, tags_prop_name, temp_tags)


class AmiConfig(BaseClass):
    """
    Handles specific configuration for the "ami" section of the config.
    """
    def __init__(self, config):
        self.parse_config(config)

class InstanceConfig(BaseClass):
    """
    Handles specific configuration for the "builder_instance" section of the config.
    """
    def __init__(self, config):
        self.parse_config(config)
        self.process_userdata_file()
    def process_userdata_file(self):
        """
	Attempts to process userdata_script file
	property on self and convert it to string.
	If it fails it just sets to blank. 
	"""
	userdata = ""
	try:
	    with open(self.userdata_script,'rb') as f:
		self.userdata = "".join(f.readlines())
	except:
	    self.userdata = ""

                    
class Config(BaseClass):
    """
    Orchestrates processing of entire config file and
    builds sub config classes as attributes of self.
    """
    def __init__(self, config):
        self.parse_config(config)
    def parse_config(self, config):
        for section in config:
            bi = section.get("builder_instance")
            ami = section.get("ami")
            gen = section.get("general")
            if bi is not None:
                self.builder_instance = InstanceConfig(bi)
            if ami is not None:
                self.ami = AmiConfig(ami)
            if gen is not None:
                for prop,val in gen.iteritems():
                    setattr(self, prop, val)
    def dump(self):
    	print("General")
    	print(self.dumpself())
        print("builder_instance")	
        print self.builder_instance.dumpself()
        print("ami")	
        print self.ami.dumpself()


def poll_until_stopped(client, instanceId):
    """
    Continuously checks on a given instance ID to see if
    it's done stopping yet. Blocks until stopped. 
    """
    max_polling_attempts = 200
    counter = 0
    while True:
        counter += 1
        if counter > max_polling_attempts:
            break
        print("Polling %d of %d" % (counter, max_polling_attempts))
        print("\tGetting status of source instance: %s" % instanceId)
        state = "unknown"
        try:
            response = client.describe_instances(
                    InstanceIds=[
                            instanceId,
                    ]
            )
            state = response.get("Reservations")[0].get("Instances")[0].get("State").get("Name")
        except Exception as er:
            print("Exception describing instances: " + str(er))

        print("\tState = %s" % state)
        if state == "stopped":
            break
        time.sleep(20)

def parse_config(filename):
    """
    Parses the given yaml config filename and
    attempts to create and return configuration objects
    """
    with open(filename,'rb') as f:
        config = yaml.load(f)
    cobj = Config(config)
    # cobj.dump()
    return cobj


def snap(client, vol_id, cobj):
    """
    Creates a snapshot of the given volume ID and tags it
    with the tags from the given config object (cobj)
    """
    response = client.create_snapshot(
        VolumeId=vol_id,
        TagSpecifications=[
            {
            "ResourceType": "snapshot",
            "Tags": cobj.ami.snapshot_tags
            }
            ]
        )
    print response
    return response.get("SnapshotId")


def image(client, snapshot_id, cobj):
    """
    Registers an AMI from a provided snapshot_id.
    Tags it using tags from config (cobj) and 
    returns the image ID.
    """
    description = ""
    name = ""
    foundname = False
    for tag in cobj.ami.ami_tags:
	if tag.get("Key") == "Name":
	    foundname = True
            name = tag.get("Value")
        if tag.get("Key") == "Description":
            description = tag.get("Value")
    if not foundname:
	timestamp = datetime.datetime.strftime(datetime.datetime.now(), cobj.ami.ami_name_timestamp_format) 
        name = cobj.ami.ami_name_prefix + timestamp
	nametag = {
	    "Key": "Name",
	    "Value": name
	}
	cobj.ami.ami_tags.append(nametag)
    response = client.register_image(
            Architecture='x86_64',
            BlockDeviceMappings=[
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {
                        "SnapshotId": snapshot_id,
                        "VolumeType": "gp2",
                    },
                },
            ],
            EnaSupport=True,
            Description=description,
            Name=name,
            RootDeviceName="/dev/sda1",
            VirtualizationType="hvm"
    )
    print response
    imageId = response.get("ImageId")
    response = client.create_tags(
            Resources=[
                imageId
            ],
            Tags=cobj.ami.ami_tags
    )
    return imageId

def create_instance(client, cobj):
    """
    Creates an instance based on information from the 
    providec configuration object (cobj). Some parameters
    are configurable such as starter AMI, subnet, userdata,
    tags but most are fixed. It will create an instance with
    two volumes (one root and one additional) and then add
    additional tags from the passed in configuration.
    """
    response = client.run_instances(
        DryRun=False,
        ImageId=cobj.builder_instance.starter_ami,
        MinCount=1,
        MaxCount=1,
        KeyName=cobj.builder_instance.key_name,
        SecurityGroupIds=[
            cobj.builder_instance.security_group,
        ],
        InstanceType=cobj.builder_instance.instance_type,
        UserData=cobj.builder_instance.userdata,
        BlockDeviceMappings=[
            {
                'DeviceName': "/dev/sda1",
                'Ebs': {
                    'VolumeSize': cobj.builder_instance.root_volume_size_gb,
                    'DeleteOnTermination': True,
                    'VolumeType': 'gp2',
                }
            },
            {
                'DeviceName': "/dev/sdf",
                'Ebs': {
                    'VolumeSize': cobj.builder_instance.builder_volume_size_gb,
                    'DeleteOnTermination': True,
                    'VolumeType': 'gp2',
                }
            },
        ],
        Monitoring={
            'Enabled': False
        },
        SubnetId=cobj.builder_instance.subnet,
        DisableApiTermination=False,
        InstanceInitiatedShutdownBehavior='stop',
        EbsOptimized=False
    )

    # grab some stats from the resulting instance
    instanceId = response.get('Instances')[0].get('InstanceId')

    # make sure to tag the instance with additional tags
    response = client.create_tags(
        DryRun = False,
        Resources = [
            instanceId,
        ],
        Tags = cobj.builder_instance.tags
    )
    return instanceId

def get_volume_id(client, instanceId):
    response = client.describe_instances(
            InstanceIds=[instanceId]
            )
    vol_id = ""
    for vol in response.get('Reservations')[0].get('Instances')[0].get("BlockDeviceMappings"):
        if vol.get("DeviceName") == "/dev/sdf":
            vol_id = vol.get("Ebs").get("VolumeId")
    return vol_id

def main():
    if len(sys.argv) < 1:
        print "Usage: python %s <config-file>" % sys.argv[0]
        sys.exit(1)
    configfile = sys.argv[1]
    try:
	cobj = parse_config(configfile)
    except Exception as err:
        print("Error processing config, exiting: " + str(err))
	sys.exit(1)
    print("Successfully parsed config. Establishing boto3 session...")

    # now set up session and client
    session = boto3.session.Session(profile_name=cobj.creds_profile_name)
    client = session.client('ec2')

    print("Creating builder instance...")
    # now create the builder instance
    instanceId = create_instance(client, cobj)
    # NOTE: It is assumed that the userdata script will stop the instance
    # when it's done performing the partitioning. 
    print("Created instance with InstanceID: %s" % instanceId)
    poll_until_stopped(client, instanceId)

    print("Grabbing volume id...")
    vol_id = get_volume_id(client, instanceId)
    print("Got volume id: %s" % vol_id)

    # now create a snapshot and register ami
    print("Now attempting to snapshot volume and create AMI...")
    sid = snap(client, vol_id, cobj)
    print("Created Snapshot with id: %s" % sid)
    iid = image(client, sid, cobj)
    print("Created AMI with id: %s" % iid)

    print("Success!")
if __name__ == "__main__":
    main()
