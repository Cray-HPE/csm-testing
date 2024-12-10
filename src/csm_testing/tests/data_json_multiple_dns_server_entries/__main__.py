#
# MIT License
#
# (C) Copyright 2022, 2024 Hewlett Packard Enterprise Development LP
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
"""
Parses data.json and prints the number of dns-server entries found in the global meta-data
"""

import logging
import sys
import csm_testing.lib.data_json_parser as dp


def main() -> int:  # pylint: disable=missing-function-docstring
    logging.basicConfig(filename='/tmp/data_json_dns_server_test.log',
                        level=logging.DEBUG)
    logging.info("Starting up")

    # Goss sends [.Args.datajson] as string with the brackets
    filename = sys.argv[1].strip('[').strip(']')
    logging.debug("Using file: %s", filename)
    data_json = dp.DataJson(filename)
    glbal = data_json.payload['Global']['meta-data']

    count = 0
    for k in glbal:
        if k == 'dns-server':
            count += 1

    print(count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
