#! /usr/bin/env python3

import os.path
import sys
import lib.data_json_parser as dp

if __name__ == '__main__':
    if os.path.isfile('/mnt/configs/data.json'):
        data_file = '/mnt/configs/data.json'
    elif os.path.isfile('/var/www/ephemeral/configs/data.json'):
        data_file = '/var/www/ephemeral/configs/data.json'
    else:
        sys.exit("Could not find data.json")


    dj = dp.dataJson()
    glbal = dj.payload['Global']['meta-data']

    count = 0
    for k in glbal:
        if k == 'dns-server':
            count += 1

    print(count)
    

