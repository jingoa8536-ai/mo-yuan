"""打包手机全量包"""

import logging
logger = logging.getLogger(__name__)

import zipfile, os

with zipfile.ZipFile('D:/LAAP/aris_brain/laap_mobile_v3_full.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, fnames in os.walk('D:/LAAP/aris_brain/mobile_package'):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fname in fnames:
            if fname.endswith('.pyc'): continue
            src = os.path.join(root, fname)
            arcname = os.path.relpath(src, 'D:/LAAP/aris_brain/mobile_package')
            arcname = arcname.replace(os.sep, '/')
            z.write(src, arcname)
            info = z.getinfo(arcname)
            logger.info(f'  {arcname:35s} {info.file_size:>8} bytes')
logger.info(f'\n总大小: {os.path.getsize("D:/LAAP/aris_brain/laap_mobile_v3_full.zip")/1024:.0f}KB')