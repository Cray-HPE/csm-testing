#
# MIT License
#
# (C) Copyright 2022, 2024-2025 Hewlett Packard Enterprise Development LP
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
from argparse import ArgumentParser
from functools import lru_cache
import json
import sys
import subprocess

import boto3
from botocore.exceptions import ClientError
from boto3.s3.transfer import TransferConfig


def main():  # pylint: disable=missing-function-docstring
    parser = ArgumentParser(
        description='check which function to execute and get parameters')
    # possible functions to execute
    parser.add_argument('--create-bucket',
                        action='store_true',
                        required=False,
                        help='creates a new bucket')
    parser.add_argument('--upload',
                        action='store_true',
                        required=False,
                        help='get a presigned url and upload a file')
    parser.add_argument('--delete-bucket',
                        action='store_true',
                        required=False,
                        help='delete a specified bucket')
    parser.add_argument('--delete-file',
                        action='store_true',
                        required=False,
                        help='delete a specified file from a bucket')
    parser.add_argument('--list',
                        action='store_true',
                        required=False,
                        help='list objects from a bucket')

    # parameters for functions
    parser.add_argument('--bucket-name',
                        dest='bucket_name',
                        action='store',
                        required=True,
                        help='the name of the bucket to upload to')
    parser.add_argument('--key-name',
                        dest='key_name',
                        action='store',
                        required=False,
                        help='the key name for the object')
    parser.add_argument('--file-name',
                        dest='file_name',
                        action='store',
                        required=False,
                        help='the file to upload')

    args = parser.parse_args()

    if args.upload:
        if (args.key_name is None or args.file_name is None
                or args.file_name is None):
            print("Error: to get presigned url, must specify --bucket-name, "
                  "--key-name, and --file-name")
            sys.exit(1)
        get_url_and_upload(args.bucket_name, args.key_name, args.file_name)
    elif args.create_bucket:
        create_bucket(args.bucket_name)
    elif args.delete_bucket:
        delete_bucket(args.bucket_name)
    elif args.delete_file:
        if args.key_name is None:
            print("Error: to delete a file, must specify --file-name")
            sys.exit(1)
        delete_object(args.bucket_name, args.key_name)
    elif args.list:
        list_objects(args.bucket_name)
    else:
        print(
            "Must specify which funciton to call. Options are --create_bucket, --delete-bucket, "
            "--upload, --delete-file, --list")


@lru_cache()
def get_credentials() -> dict:
    """get credentials"""
    jdata = json.loads(
        subprocess.check_output(
            ['radosgw-admin', 'user', 'info', '--uid', 'STS']))
    keys = ((jdata['keys'])[0])
    return {
        'endpoint_url': 'http://rgw-vip.nmn',
        'access_key': keys['access_key'],
        'secret_key': keys['secret_key']
    }


def create_bucket(bucket_name):
    credentials = get_credentials()
    s3_resource = boto3.resource(
        's3',
        endpoint_url=credentials['endpoint_url'],
        aws_access_key_id=credentials['access_key'],
        aws_secret_access_key=credentials['secret_key'])

    bucket = s3_resource.Bucket(bucket_name)
    bucket.create()


def delete_bucket(bucket_name):
    credentials = get_credentials()
    s3_resource = boto3.resource(
        's3',
        endpoint_url=credentials['endpoint_url'],
        aws_access_key_id=credentials['access_key'],
        aws_secret_access_key=credentials['secret_key'])

    bucket = s3_resource.Bucket(bucket_name)
    bucket.delete()


def get_url_and_upload(bucket_name, key_name, file_name):

    # One week
    expires = 604800
    credentials = get_credentials()
    s3_client = boto3.client(
        's3',
        aws_access_key_id=credentials['access_key'],
        aws_secret_access_key=credentials['secret_key'],
        endpoint_url=credentials['endpoint_url'],
        region_name='',
    )

    try:
        s3_client.put_object(Bucket=bucket_name,
                             Key=key_name,
                             ACL='public-read')
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': key_name
            },
            ExpiresIn=expires,
        )
    except s3_client.exceptions.NoSuchBucket as err:
        sys.exit(str(err))
    except ClientError as err:
        try:
            s3_client.delete_object(Bucket=bucket_name, Key=key_name)
        except Exception as delete_err:
            print(
                f"Unsuccessful upload. Unable to delete object: Error: {delete_err}"
            )
        sys.exit(str(err))

    try:
        upload_args = (file_name, bucket_name, key_name)
        config = TransferConfig(use_threads=False)
        upload_kwargs = {
            'Config': config,
            'ExtraArgs': {
                'Metadata': {
                    'download_url': url,
                }
            }
        }
        s3_client.upload_file(*upload_args, **upload_kwargs)
        print(url)

    except ClientError as err:
        try:
            s3_client.delete_object(Bucket=bucket_name, Key=key_name)
        except Exception as delete_err:
            print(
                f"Unsuccessful upload. Unable to delete object: Error: {delete_err}"
            )
        sys.exit(str(err))


def list_objects(bucket_name):
    credentials = get_credentials()
    s3_client = boto3.client('s3',
                             endpoint_url=credentials['endpoint_url'],
                             aws_access_key_id=credentials['access_key'],
                             aws_secret_access_key=credentials['secret_key'])

    response = s3_client.list_objects_v2(Bucket=bucket_name)
    if 'Contents' not in response:
        print('No objects in bucket')
    else:
        for item in response['Contents']:
            print(item['Key'])


def delete_object(bucket_name, key_name):
    credentials = get_credentials()
    s3_client = boto3.client('s3',
                             endpoint_url=credentials['endpoint_url'],
                             aws_access_key_id=credentials['access_key'],
                             aws_secret_access_key=credentials['secret_key'])

    s3_client.delete_object(Bucket=bucket_name, Key=key_name)


if __name__ == '__main__':
    main()
