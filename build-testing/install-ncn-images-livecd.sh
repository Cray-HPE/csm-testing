#!/usr/bin/env bash
# Installs NCN image files on the LiveCD.
#
# (C) Copyright 2021 Hewlett Packard Enterprise Development LP.
# Author: Forrest Jadick
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

# usage: install-ncn-images-livecd.sh -k [k8s image version #/id] -s [ceph image version #/id]

k8s_image_id=$2
ceph_image_id=$4

# hide old image files
echo "Cleaning up old install directories..."
rm -rf /var/www/ephemeral/data/.ceph
rm -rf /var/www/ephemeral/data/.k8s
mv /var/www/ephemeral/data/{,.}ceph
mv /var/www/ephemeral/data/{,.}k8s

# delete all node directories
echo "Removing node directories..."
rm -rf /var/www/ncn-*

cd /root

# pull images
echo "Pulling NCN image files..."
/root/bin/get-sqfs.sh -k $k8s_image_id
/root/bin/get-sqfs.sh -s $ceph_image_id

# install images
echo "Installing images in /var/www..."
/root/bin/set-sqfs-links.sh

exit