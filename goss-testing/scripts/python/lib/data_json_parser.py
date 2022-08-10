#!/usr/bin/env python2
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
from __future__ import print_function

"""
dataJson is a convenience class to work with the data.json file

data.json exists as key:value file where key can be either a mac address that is inconsistent depending on the environment
Or ... everything else - which IS consistent Storage, Default, Global, etc. 
Convenience functions are included to easily dig out the most likely needed data

Parameters:
dataJson(/path/to/data.json) 

Exposes:
    payload: A dictionary of the entire data.json file
    keys: A list of all of the keys
    ncnKeys: A list of only the ncn keys (the MAC address of each ncn)
    otherKeys: A list of the non-ncn keys
    ncnList: A list of k:v dictionaries, where k==ncn name and v==the MAC address. Easier for me to read

Functions:
    getGlobalMD(self):      Convenience function that returns just the Global meta-data
    getNcnData(self, ncn):  Convenience function - reverse lookup by hostname and return all of values
    getNcnDataM(self, ncn): Convenience function - reverse lookup by hostname and return just the meta-data
    getNcnDataU(self, ncn): Convenience function - reverse lookup by hostname and return the user-data

"""

import json
import re

class dataJson:
    def __init__(self, data_json_path='/mnt/configs/data.json'):
        self.macRegex = re.compile('[a-f,0-9][a-f,0-9]:[a-f,0-9][a-f,0-9]:[a-f,0-9][a-f,0-9]:[a-f,0-9][a-f,0-9]:[a-f,0-9][a-f,0-9]:[a-f,0-9][a-f,0-9]')
        #self.objFile = 'data.json'
        self.objFile = data_json_path

        with open(self.objFile) as obj:
            try:
                self.payload = json.load(obj)
            except:
                print("Unable to open " + objFile + ". Possibly malformed json?")
                sys.exit()

        self.keys = self.payload.keys()
        self.ncnKeys = []
        self.otherKeys = []

        # sort through the keys - if they match the MAC address regex - they are ncns
        for key in self.keys:
            if self.macRegex.match(key):
                self.ncnKeys.append(key)
            else:
                self.otherKeys.append(key)

        # Make a dictionary of all the ncns for easy checking
        self.ncnList = {}
        for ncnKey in self.ncnKeys:
            self.ncnList[self.payload[ncnKey]['user-data']['hostname']] = ncnKey

    def getGlobalMD(self):
        '''Convenience function that returns just the Global mete-data'''
        return self.payload['Global']['meta-data']

    def getNcnData(self, ncn):
        '''Convenience function to reverse lookup the data and returns it by ncn hostname'''
        return self.payload[self.ncnList[ncn]]

    def getNcnDataM(self, ncn):
        '''Convenience function - reverse lookup by hostname and return just the meta-data'''
        return self.payload[self.ncnList[ncn]]['meta-data']

    def getNcnDataU(self, ncn):
        '''Convenience function - reverse lookup by hostname and return the user-data'''
        return self.payload[self.ncnList[ncn]]['user-data']

if __name__ == '__main__':
    # this is just for testing purposes
    dj = dataJson()
    print (dj.keys)
    for key in dj.ncnKeys:
        print (key)

    print(dj.payload)
    print(dj.getNcnDataU('ncn-w001'))

