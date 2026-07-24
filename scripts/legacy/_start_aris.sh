#!/bin/bash
# Start Aris Feishu Bridge
cd /opt/aris
source venv/bin/activate
export FEISHU_APP_ID=cli_aaa4a20527f9dbd6
export FEISHU_APP_SECRET=***python3 -u -c "
import sys
sys.path.insert(0, '/opt/aris')
import aris_fly_bridge
"
