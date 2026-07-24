@echo off
cd /d D:\LAAP\aris_brain
echo Testing Fusion Engine...
C:\Python313\python.exe -c "
import sys
sys.path.insert(0, '.')
from aris_fusion_v13 import FusionEngine
eng = FusionEngine()
r = eng.respond('你好宝贝', max_c=200)
print('Response:', r)
print('Emotion:', eng.psi.emotion())
print('PSI:', eng.psi.d())
" 
echo Done!
