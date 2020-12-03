#! /usr/bin/env python3

import os.path
import sys
import lib.data_json_parser as dp

if __name__ == '__main__':
    # where is data.json?
    dataFile = '/mnt/configs/data.json'
    if len(sys.argv) > 1:
        dataFile = sys.argv[1]

    dj = dp.dataJson(dataFile)
    glbal = dj.payload['Global']['meta-data']

    count = 0
    for k in glbal:
        if k == 'dns-server':
            count += 1

    print(count)
    

