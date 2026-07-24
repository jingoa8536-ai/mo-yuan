"""Check ollama models directories."""

import logging
logger = logging.getLogger(__name__)

import os

# Check default location
default = os.path.expanduser('~/.ollama/models/blobs')
if os.path.exists(default):
    blobs = os.listdir(default)
    logger.info(f"Default location ({default}):")
    logger.info(f"  {len(blobs)} blobs")
    total = sum(os.path.getsize(os.path.join(default, b)) for b in blobs)
    logger.info(f"  Total: {total/1e9:.1f} GB")
    for b in sorted(blobs):
        sz = os.path.getsize(os.path.join(default, b))
        logger.info(f"    {sz/1e9:.2f}GB  {b}")
else:
    logger.info(f"Default location not found: {default}")
custom = 'D:/ollama/models/blobs'
if os.path.exists(custom):
    blobs = os.listdir(custom)
    logger.info(f"\nCustom location ({custom}):")
    logger.info(f"  {len(blobs)} blobs")
    total = sum(os.path.getsize(os.path.join(custom, b)) for b in blobs)
    logger.info(f"  Total: {total/1e9:.1f} GB")
    for b in sorted(blobs):
        sz = os.path.getsize(os.path.join(custom, b))
        logger.info(f"    {sz/1e9:.2f}GB  {b}")
else:
    logger.info(f"\nCustom location not found: {custom}")
for base in [default, custom]:
    if os.path.exists(base):
        manifest_dir = os.path.join(os.path.dirname(base), 'manifests')
        if os.path.exists(manifest_dir):
            logger.info(f"\nManifests in {manifest_dir}:")
            for root, dirs, files in os.walk(manifest_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    rp = os.path.relpath(fp, manifest_dir)
                    sz = os.path.getsize(fp)
                    logger.info(f"    {rp} ({sz} bytes)")