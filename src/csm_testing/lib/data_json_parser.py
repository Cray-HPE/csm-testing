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
DataJson is a convenience class to work with the data.json file

data.json exists as key:value file where key can be either a mac address that is inconsistent
depending on the environment
Or ... everything else - which IS consistent Storage, Default, Global, etc.
Convenience functions are included to easily dig out the most likely needed data

Parameters:
DataJson(/path/to/data.json)

Exposes:
    payload: A dictionary of the entire data.json file
    keys: A list of all of the keys
    ncn_keys: A list of only the ncn keys (the MAC address of each ncn)
    other_keys: A list of the non-ncn keys
    ncn_list: A list of k:v dictionaries, where k==ncn name and v==the MAC address. Easier for
             me to read

Functions:
    get_global_md(self):      Convenience function that returns just the Global meta-data
    get_ncn_data(self, ncn):  Convenience function - reverse lookup by hostname and return all of
                            values
    get_ncn_data_m(self, ncn): Convenience function - reverse lookup by hostname and return just the
                            meta-data
    get_ncn_data_u(self, ncn): Convenience function - reverse lookup by hostname and return the
                            user-data
"""

from __future__ import print_function
import json
import re
import sys


class DataJson:

    def __init__(self, data_json_path='/mnt/configs/data.json'):
        self.mac_regex = re.compile(
            r'[a-f,0-9][a-f,0-9]:[a-f,0-9][a-f,0-9]:[a-f,0-9][a-f,0-9]:'
            r'[a-f,0-9][a-f,0-9]:[a-f,0-9][a-f,0-9]:[a-f,0-9][a-f,0-9]')
        #self.obj_file = 'data.json'
        self.obj_file = data_json_path

        with open(self.obj_file) as obj:
            try:
                self.payload = json.load(obj)
            except:
                print("Unable to open " + self.obj_file +
                      ". Possibly malformed json?")
                sys.exit()

        self.keys = self.payload.keys()
        self.ncn_keys = []
        self.other_keys = []

        # sort through the keys - if they match the MAC address regex - they are ncns
        for key in self.keys:
            if self.mac_regex.match(key):
                self.ncn_keys.append(key)
            else:
                self.other_keys.append(key)

        # Make a dictionary of all the ncns for easy checking
        self.ncn_list = {}
        for ncn_key in self.ncn_keys:
            self.ncn_list[self.payload[ncn_key]['user-data']
                          ['hostname']] = ncn_key

    def get_global_md(self):
        '''Convenience function that returns just the Global mete-data'''
        return self.payload['Global']['meta-data']

    def get_ncn_data(self, ncn):
        '''Convenience function to reverse lookup the data and returns it by ncn hostname'''
        return self.payload[self.ncn_list[ncn]]

    def get_ncn_data_m(self, ncn):
        '''Convenience function - reverse lookup by hostname and return just the meta-data'''
        return self.payload[self.ncn_list[ncn]]['meta-data']

    def get_ncn_data_u(self, ncn):
        '''Convenience function - reverse lookup by hostname and return the user-data'''
        return self.payload[self.ncn_list[ncn]]['user-data']


if __name__ == '__main__':
    # this is just for testing purposes
    dj = DataJson()
    print(dj.keys)
    for ncn_key in dj.ncn_keys:
        print(ncn_key)

    print(dj.payload)
    print(dj.get_ncn_data_u('ncn-w001'))
