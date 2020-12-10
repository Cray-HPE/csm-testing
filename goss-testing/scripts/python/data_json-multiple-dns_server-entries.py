#! /usr/bin/env python3

import lib.data_json_parser as dp
import sys, logging

logging.basicConfig(filename='/tmp/data_json_dns_server_test.log', level=logging.DEBUG)
logging.info("Starting up")
if __name__ == '__main__':
    # Goss sends [.Args.datajson] as string with the brackets
    filename = sys.argv[1].strip('[').strip(']')
    logging.debug("Using file: %s", filename)
    dj = dp.dataJson(filename)
    glbal = dj.payload['Global']['meta-data']

    count = 0
    for k in glbal:
        if k == 'dns-server':
            count += 1

    print(count)
    

