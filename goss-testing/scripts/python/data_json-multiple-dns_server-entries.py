#! /usr/bin/env python3

import lib.data_json_parser as dp

if __name__ == '__main__':
    dj = dp.dataJson()
    glbal = dj.payload['Global']['meta-data']

    count = 0
    for k in glbal:
        if k == 'dns-server':
            count += 1

    print(count)
    

