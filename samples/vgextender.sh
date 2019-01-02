#!/bin/bash
# 
# Extends LVM volume group and fills remaining
# space for /, /var, and /home partitions
#

TGTDEV=/dev/nvme0n1
NEWPART=p3
NEWDEV=$TGTDEV$NEWPART

# show free space before
df -h

# partition remaining space as new drive

# to create the partitions programatically (rather than manually)
# we're going to simulate the manual input to fdisk
# The sed script strips off all the comments so that we can
# document what we're doing in-line with the actual commands
# Note that a blank line (commented as "defualt" will send a empty
# line terminated with a newline to take the fdisk default.
sed -e 's/\s*\([\+0-9a-zA-Z]*\).*/\1/' << EOF | fdisk ${TGTDEV}
  n # new partition
  p # primary partition
  3 # partition number 1
    # default - start at end of last partition
    # default - all remaining space
  t # set partition type
  3 # select third partition
  8e # set to Linux LVM
  p # print the in-memory partition table
  w # write the partition table
  q # and we're done
EOF

# run partprobe to re-read partition table
partprobe

# now create a new PV, extend the Volume Group, and extend the logical volumes
pvcreate $NEWDEV
vgextend vg1 $NEWDEV
lvextend -l 30%VG /dev/vg1/root
lvextend -l 40%VG /dev/vg1/var
lvextend -l 30%VG /dev/vg1/home
xfs_growfs /dev/vg1/root
xfs_growfs /dev/vg1/var
xfs_growfs /dev/vg1/home

# show new free space
df -h
