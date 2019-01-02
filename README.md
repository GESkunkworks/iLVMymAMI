# iLVMymAMI

Notes and scripts for repartitioning a volume with LVM from an existing marketplace AMI.

![](./img/lvm.png)

## Background and Approach
On \*Nix based systems it is generally considered best practice to create separate partitions for `/var` and `/home` so that they are isolated from `/`. This has the advantage of preventing a rogue user from filling up the root volume with large files and crashing the system or a rogue process filling up `/var/log` and causing issues with processes that need to modify the root filesystem. Some would argue even further isolation via `/var/log` and `/tmp`. It all depends on your use case. More discussion on the topic can be found [here](https://access.redhat.com/discussions/641923). 

Additionally, it's nice to have the main mount points of your system running on LVM so that the filesystems can grow and shrink as needed. This is also a very opinionated way to setup a base operating system disk and some would argue it's becoming less relevant as we move towards cloud and virtualization.

However, for our use cases I believe that we need to keep `/var` and `/home` isolated from `/` and if we have to do that anyway we might as well do it with LVM so we have filesystem flexibility later. Therefore, this guide covers the method of taking an AWS Marketplace AMI and re-partitioning it as LVM and registering it as a new AMI. 

## Automatic Image Creation
If you want to just take an existing CentOS AMI and create an LVM version of it you can try using the script provided here. 

Create a config file using `config-sample.yml` as a template and then run:

```
python ilvmymami.py config.yml
```

The script will attempt the following:
1. create an instance with an additional volume with `parter-centos.sh` as userdata
1. the userdata will attempt to prepare the additional volume as LVM and clone the builder instance's root volume to it and then shut down
1. the script will then attempt to snapshot and register the volume as an AMI using tags you provide in the config file.

Hopefully the above will work for you however it may be finicky. Below is an overview of the manual steps for the process. 

# Manual Run
## Prereqs

1. Launch an `m5` class instance from desired source AMI. In this case we'll use a CentOS image from the marketplace that's been lightly modified (patched and user updated)
1. Shut down the instance once it's launched.
1. Create a new blank volume and attach it to the instance you just launched as `/dev/sdf`
   * NOTE: Make sure the volume is in the same AZ as the instance you just created
1. Start the instance and SSH to it.

## Steps
This will be a walkthrough of the steps in the `parter-centos.sh` script.

#### Partition the New Drive
1. First switch to root with `sudo su -`
1. Run `fdisk -l` and find out what your new device name is. In my case it was `/dev/nvme1n1`. 
1. Run `fdisk /dev/nvme1n1` to start partitioning the new attached volume.
1. First set the drive as `msdos` mode by hitting `o`. The alternative is `gpt` which isn't covered in this guide.
1. Hit `n` to create a new partition.
1. Set it as partition 1 and hit Enter to accept the default start position.
1. For the end position instead of using a sector we'll just say `+500M` to set a 500 MB partition.
1. Make another new partition by hitting `n` and making it partition 2. Just hit enter twice in a row to have this one fill the remaining space on the drive.
1. Now set the partition type to `Linux LVM` by hitting `t`, selecting partition 2, and setting the type code as `8e`
1. Make partition 1 bootable by hitting `a` and selecting partition 1.
1. You can print the results of the table by hitting `p`. (see sample output below)
1. Write the partition table with `w` and then hit `q` to exit the partitioner.

Sample partition table
```
Disk /dev/nvme0n1: 53.7 GB, 53687091200 bytes, 104857600 sectors
Units = sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 512 bytes
I/O size (minimum/optimal): 512 bytes / 512 bytes
Disk label type: dos
Disk identifier: 0x61cdaa0a

        Device Boot      Start         End      Blocks   Id  System
/dev/nvme0n1p1   *        2048     1026047      512000   83  Linux
/dev/nvme0n1p2         1026048    16777215     7875584   8e  Linux LVM
```

#### Setup LVM on the New Drive
Here we'll carve out the LVM partition with our desired partitions for `/home`, `/var`, and `/`.

1. Make sure you have LVM utilities installed by running `yum install lvm2 -y`
1. 

... To be continued


## Credit
Thanks to Alex Y from AWS support for helping with some blockers in this process.

Credit to [Bob Plankers](https://lonesysadmin.net/2013/03/26/preparing-linux-template-vms/) for a lot of these tips.

