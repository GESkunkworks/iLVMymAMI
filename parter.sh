#!/bin/bash

# This script partitions an additional volume 
# as LVM with separate /home, /var, /boot, and /
# partitions attached to a CentOS server
# and then clones itself to the volume. It then
# prepares the volume as bootable with the intent
# that the volume can be registered as an AWS AMI
#
# It can be run manually or as a userdata script
# passed to an instance. 
#
# NOTE: When run as userdata please try to keep
# output to a minimum as it can overload the 
# serial device logger in AWS. 


# This is the target volume that will be prepared
# for the clone. 
TGTDEV=/dev/nvme1n1
VOLGROUPNAME=vg1


# to create the partitions programatically (rather than manually)
# we're going to simulate the manual input to fdisk
# The sed script strips off all the comments so that we can 
# document what we're doing in-line with the actual commands
# Note that a blank line (commented as "defualt" will send a empty
# line terminated with a newline to take the fdisk default.
sed -e 's/\s*\([\+0-9a-zA-Z]*\).*/\1/' << EOF | fdisk ${TGTDEV}
  o # clear the in memory partition table
  n # new partition
  p # primary partition
  1 # partition number 1
    # default - start at beginning of disk 
  +500M # 500 MB boot parttion
  n # new partition
  p # primary partition
  2 # partion number 2
    # default, start immediately after preceding partition
    # default, extend partition to end of disk
  t # set partition type
  2 # select second partition
  8e # set to Linux LVM
  a # make a partition bootable
  1 # bootable partition is partition 1 
  p # print the in-memory partition table
  w # write the partition table
  q # and we're done
EOF

# make sure lvm2 is installed
yum install lvm2 -y

# setup LVM and create filesystems
P1=p1
P2=p2
LVMDEV=$TGTDEV$P2
BOOTDEV=$TGTDEV$P1
pvcreate $LVMDEV
vgcreate vg1 $LVMDEV
lvcreate -l 30%VG -n root $VOLGROUPNAME
lvcreate -l 40%VG -n var $VOLGROUPNAME
lvcreate -l 30%VG -n home $VOLGROUPNAME
mkfs.xfs $BOOTDEV -L /boot
mkfs.xfs /dev/$VOLGROUPNAME/root -L /
mkfs.xfs /dev/$VOLGROUPNAME/var
mkfs.xfs /dev/$VOLGROUPNAME/home

# create mount points and mount new filesystems
mkdir -p /mnt
mount /dev/$VOLGROUPNAME/root /mnt 
mkdir -p /mnt/var
mount /dev/$VOLGROUPNAME/var /mnt/var
mkdir -p /mnt/home
mount /dev/$VOLGROUPNAME/home /mnt/home
mkdir -p /mnt/boot
mount $BOOTDEV /mnt/boot

# Copy files from host system to new volume, make sure to exclude the nasties
rsync -axHAX --exclude='{"/dev/*","/proc/*","/sys/*","/tmp/*","/run/*","/mnt/*","/media/*","/srv/*","/newsysroot"}' / /mnt/

# might have to make sure target filesystem has lvm2 modules installed
yum install --installroot /mnt lvm2 -y

# Mount some necessary paths from host so we can prep for building initramfs
mkdir -p /mnt/proc
mount -o bind /proc /mnt/proc
mkdir -p /mnt/sys
mount -o bind /sys /mnt/sys
mkdir -p /mnt/dev
mount -o bind /dev /mnt/dev

# create the script we're gonna run inside chroot
touch chrooter.sh
echo "#!/bin/bash" >> chrooter.sh
echo "dracut -f -v" >> chrooter.sh
echo "grub2-mkconfig -o /boot/grub2/grub.cfg" >> chrooter.sh
echo "grub2-install $TGTDEV" >> chrooter.sh
chmod +x chrooter.sh
cp chrooter.sh /mnt/root/chrooter.sh
# now jump into filesystem and run the script we just generated then jump back
chroot /mnt /root/chrooter.sh

# now build fstab
# grab current UUIDs for devices
uuidroot="$(blkid /dev/$VOLGROUPNAME/root | gawk 'match($0, /UUID=\"([^,"]+)"/, uid) { print uid[1]}')"
uuidhome="$(blkid /dev/$VOLGROUPNAME/home | gawk 'match($0, /UUID=\"([^,"]+)"/, uid) { print uid[1]}')"
uuidvar="$(blkid /dev/$VOLGROUPNAME/var | gawk 'match($0, /UUID=\"([^,"]+)"/, uid) { print uid[1]}')"
uuidboot="$(blkid $BOOTDEV | gawk 'match($0, /UUID=\"([^,"]+)"/, uid) { print uid[1]}')"

# and blow away current fstab on build volume
echo "UUID=$uuidroot /                       xfs     defaults        0 0" > /mnt/etc/fstab
echo "UUID=$uuidhome /home                       xfs     defaults        0 0" >> /mnt/etc/fstab
echo "UUID=$uuidvar /var                       xfs     defaults        0 0" >> /mnt/etc/fstab
echo "UUID=$uuidboot /boot                       xfs     defaults        0 0" >> /mnt/etc/fstab

cat /mnt/etc/fstab

# CentOS 7 comes with SELinux in Enforcing mode by default, so AWS suggeste adding /.autorelabel file to relabel all files upon reboot (you can disregard this step if SELinux is not active):
touch /.autorelabel

# unmount everything
umount -R /mnt

sleep 3

# unmap the VG on the host
vgchange -an vg1

# and shutdown
shutdown -h now
