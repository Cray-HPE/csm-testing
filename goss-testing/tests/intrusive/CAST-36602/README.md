# Overview

Approximately 960 Paradise nodes were loaded into SLS as two dual node chassis
instead of single quad node chassis.  Additionally, two Paradise chassis,
totalling 8 nodes are used as Application nodes (UAN), not compute and this
combination is not well handled by CANU.

## Process

1. Fix the SHCD by recategorizing the Paradise nodes with Parents (SubRack-cmc).
2. Generate a full CCJ/Paddle file with CANU.
3. Scrub the paddle file to make cn1-8 UANs wih `ccj_scrub_uan_computes.py`
4. Dump the SLS file.
5. Scrub the SLS file file to remove all the miscategorized nodes with `sls_scrub_nids.py`.
6. Load the scrubbed SLS file back into SLS.
7. Run the Hardware Topology tool using the scrubbed CCJ and the live scrubbed SLS to add the hardware.
