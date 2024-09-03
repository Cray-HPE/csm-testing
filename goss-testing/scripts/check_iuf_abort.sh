python3 /opt/cray/tests/install/ncn/scripts/python/iuf_run.py /opt/cray/tests/install/ncn/scripts/python/iuf_run_setup test-activity & \        
sleep 10 && \
iuf -a test-activity abort -f
