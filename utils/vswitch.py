'''
vswitch.py

Switches a volume from one instance to another.
Update the profile_name for your creds and update 
instances and volid's dictionaries with your 
instances and volume id's and then run with:

    python vswitch.py

It will ask you which volume you want to move, what
the current source instance is, and what the desired 
target instance is.

First it stops the source instance, detaches the volume
then it attaches the volume to the other instance and starts it.

'''

import boto3
import time
import sys

profile_name = "public-cloud-prod"
instances = {
        1:  {"name": "c1", "id": "i-037d67f4c14a026b5", "mount": "/dev/sdf"},
        2:  {"name": "d1", "id": "i-078531f8bda92e4f8", "mount": "/dev/sda1"},
        3:  {"name": "d2", "id": "i-08c16eb847a489fe0", "mount": "/dev/sda1"},
        4:  {"name": "cheat", "id": "i-05cda464e5779ab51", "mount": "/dev/sda1"},
    }
volids = {
        1:  {"name": "cheatroot", "id": "vol-02ecd9890707de650"},
        2:  {"name": "canvas-simple", "id": "vol-048a760f6772d161a"},
    }

# vol_id = "vol-08d4fb3a5574ba038"
# vol_id = "vol-048a760f6772d161a"

def poll_until_stopped(client, instanceId):
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
        time.sleep(5)


def main():
    session = boto3.Session(profile_name=profile_name)
    client = session.client("ec2")
  
    vol_id = ""
    for i,d in volids.items():
        print("%d : %s (%s)" % (i, d.get("id"), d.get("name")))

    question = "Which volume would you like to move? (Enter a number) "

    selection_vol_string = raw_input(question)
    selection_vol_num = 0
    try:
        vol_id = volids[int(selection_vol_string)].get("id")
    except:
        print("Exception processing selection, exiting: " + str(e))
        sys.exit(1)

    for i,d in instances.items():
        print("%d : %s (%s)" % (i, d.get("id"), d.get("name")))
    
    question = "What is the source instance that %s is currently attached to? (Enter a number) " % vol_id

    selection_source_string = raw_input(question)
    selection_source_num = 0
    try:
        selection_source_num = int(selection_source_string)
    except:
        print("Exception processing selection, exiting: " + str(e))
        sys.exit(1)

    question = "What is the destination instance that you wish to attach %s to? (Enter a number) " % vol_id

    selection_dest_string = raw_input(question)
    selection_dest_num = 0
    try:
        selection_dest_num = int(selection_dest_string)
    except:
        print("Exception processing selection, exiting: " + str(e))
        sys.exit(1)

    dest_instance = instances.get(selection_dest_num)
    source_instance = instances.get(selection_source_num)
    print("Source instance: %s" % source_instance.get("id"))
    print("Destination instance: %s" % dest_instance.get("id"))

    
    try:
        response = client.stop_instances(
                InstanceIds=[
                        dest_instance.get("id"),
                ]
        )	
        response = client.stop_instances(
                InstanceIds=[
                        source_instance.get("id"),
                ]
        )	
    except Exception as e:
        print("Got exception stopping instance: " + str(e))

    poll_until_stopped(client, source_instance.get("id"))
    poll_until_stopped(client, dest_instance.get("id"))

    try:
        response = client.detach_volume(
            VolumeId=vol_id
        )
        time.sleep(5)
    except Exception as e:
        print("Got exception detaching volume: " + str(e))
   

    try:
        response = client.attach_volume(
                Device=dest_instance.get("mount"),
                InstanceId=dest_instance.get("id"),
                VolumeId=vol_id
        )
        print response
    except Exception as e:
        print("Got exception attaching volume: " + str(e))

    try:
        response = client.start_instances(
                InstanceIds=[
                        dest_instance.get("id"),
                ]
        )	
    except Exception as e:
        print("Got exception starting instance: " + str(e))

def snap_and_bake(client, vol_id):
    response = client.create_snapshot(
        VolumeId=vol_id,
        TagSpecifications=[
            {
            "Tags": [
                {
                "Key": "Name",
                "Value": "rendicott-lvm-constructor-tsnap"
                }
                ]
            }
            ]
        )
    sid = response.get("SnapshotId")


if __name__ == "__main__":
    main()
