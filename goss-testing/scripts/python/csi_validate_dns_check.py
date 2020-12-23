import sys, os
import lib.data_json_parser as dp

''' Simple test to validate dns. It mimics the CSI validate check `grep -Eo 'ncn-.*-mgmt'` 
    against data.json global meta-data ntp-peers.
Counts the number of times that the ntp-peer appears in dnsmasq.leases file
matches that to the number of ntp_peers - they should be ==
'''

PASSED = 0
dnsmasq_file = '/var/lib/misc/dnsmasq.leases'

# Assume we got the right info from goss, but JIC
if len(sys.argv) == 2:
    data_json = sys.argv[1].strip('[').strip(']')
else:
    data_json = "/var/www/ephemeral/configs/data.json"

# load the info from dnsmasq.leases
if os.path.isfile(dnsmasq_file):
    f = open(dnsmasq_file, 'r')
    dns_contents = f.read()

dj = dp.dataJson(data_json)
peers = dj.getGlobalMD()["ntp_peers"].split()

# If this machine(ncn-m001) is in data.json global meta-data ntp-peers, remove it
if 'ncn-m001' in peers:
    peers.remove('ncn-m001')

for peer in peers:
    if peer+'-mgmt' in dns_contents:
        PASSED += 1

if PASSED == len(peers):
    print("PASS")
else:
    print("FAIL")
