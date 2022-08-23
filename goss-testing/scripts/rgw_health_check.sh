#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2022 Hewlett Packard Enterprise Development LP
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
echo "---Test that rgw-vip and storage nodes are reachable---"
exit_code=0
num_snodes=$(craysys metadata get num_storage_nodes)
if [[ $? != 0 ]]
then
    echo "Error: craysys command failed, check that cloud init is working."
    num_snodes=3  # default to checking 3 storage nodes
    exit_code=3
fi

iter=1
#check that all storage nodes are up
while [[ $iter -le $num_snodes ]]
do
    nodename=$(printf "ncn-s%03d" $iter)
    response=$(curl -i -s -S http://${nodename}:8080/)
    if [[ $? != 0 ]]
    then
        echo "Unable to reach http://${nodename}:8080."
        echo "Http response: $response"
        echo
        exit_code=2
    fi
    iter=$(( $iter + 1 ))
done

#check connection to rgw-vip
response=$(curl -i -s -S -k https://rgw-vip.nmn)
if [[ $? != 0 ]]
then
    echo "Not able to connect to https://rgw-vip.nmn."
    echo "Https response: $response"
    echo
    exit_code=1
fi

response=$(curl -i -s -S http://rgw-vip.nmn)
if [[ $? != 0 ]]
then
   echo "Not able to connect to http://rgw-vip.nmn"
   echo "Http response: $response"
   echo
   exit_code=1
fi

response=$(curl -i -s -S http://rgw-vip.hmn)
if [[ $? != 0 ]]
then
   echo "Not able to connect to http://rgw-vip.hmn."
   echo "Http response: $response"
   echo
   exit_code=1
fi

if [[ $exit_code == 0 ]]
then
    echo "Passed: rgw-vip and storage nodes are responding."
elif [[ $exit_code == 3 ]]
then
    echo "Rgw-vip and storage nodes are responding."
else
    echo "Failed: Check that rgw-vip is working and storage nodes running. If vip is not up, fix by restarting keepalived on storage nodes."
    exit $exit_code # don't continue to next section if rgw-vip or storage nodes are not up
fi

echo
# check ability to upload and download using rgw, gets presigned url to upload
echo "---Test ability to upload and download a file from bucket---"
upload_file='/tmp/testing_rgw.txt'
echo "Writing to a test file. -- test {} test" > $upload_file
test_bucket='testb'
key_name='test.file'
download_file='/tmp/test_download.txt'

# check if test_bucket already exists
bucket=$(radosgw-admin bucket list | grep ${test_bucket})
if [[ ! -z $bucket ]]
then
    echo "Test bucket already exists, not creating new bucket."
else
    echo "-Created a test bucket."
    ${GOSS_BASE}/scripts/python/rgw-endpoint-check.py --create-bucket --bucket-name $test_bucket
    if [[ $? != 0 ]]
    then
        echo "Unable to create a test bucket. Exiting."
        exit 5 # all subsequent functions require this new bucket
    fi
fi
# get presigned url and upload file
url=$(${GOSS_BASE}/scripts/python/rgw-endpoint-check.py --upload --bucket-name $test_bucket --key-name $key_name --file-name ${upload_file})
# check that file is in bucket
contents=$(${GOSS_BASE}/scripts/python/rgw-endpoint-check.py --list --bucket-name $test_bucket | grep ${key_name})
if [[ ! -z $contents ]]
then
    echo "-File successfully uploaded to bucket."
else
    echo "Error uploading file to bucket."
    exit_code=4
fi
# download and check if there is a difference
curl -s ${url} -o $download_file
diff $download_file $upload_file
if [[ $? == 0 ]]
then
    echo "-Successfully downloaded file."
    rm $download_file # remove the downloaded file
else
    echo "Error downloading file from test bucket."
    exit_code=4
fi
#delete file from bucket and folder
${GOSS_BASE}/scripts/python/rgw-endpoint-check.py --delete-file --bucket-name $test_bucket --key-name $key_name
rm $upload_file
#check that file was deleted
contents=$(${GOSS_BASE}/scripts/python/rgw-endpoint-check.py --list --bucket-name $test_bucket | grep ${key_name})
if [[ -z $contents ]]
then
    echo "-File successfully deleted from bucket."
else
    echo "Error deleting file from bucket."
    exit_code=4
fi
# remove test bucket
${GOSS_BASE}/scripts/python/rgw-endpoint-check.py --delete-bucket --bucket-name $test_bucket
bucket=$(radosgw-admin bucket list | grep ${test_bucket})
if [[ -z $bucket ]]
then
    echo "-Test bucket successfully deleted."
else
    echo "Error deleting test bucket."
    exit_code=4
fi

if [[ $exit_code != 4 ]]
then
    echo "Passed: successfully uploaded and downloaded a file from bucket."
else
    echo "Error. Not able to upload or download a file from bucket."
fi

exit $exit_code
