@echo off
title LAAP - MMD Model Test
cd /d D:\LAAP\external_mmdpy
echo Testing MMD model rendering...
echo.
echo If a 3D window appears with the model, it works!
echo Close the window to exit.
echo.
python -c "
import sys
sys.path.insert(0, '.')
import mmdpy
import mmdpy_world
import glfw

print('Creating window...')
world = mmdpy_world.world('mmdpy', 640, 480)

print('Loading model...')
m = mmdpy.model()
if m.load(r'D:\LAAP\laap\web\static\models\model.pmx'):
    print('Model loaded OK!')
    world.push(m)
    
    print('Rendering...')
    import time
    timeout = time.time() + 30
    while not glfw.window_should_close(world.window) and time.time() < timeout:
        world.run()
    
    world.close()
    print('Done')
else:
    print('FAILED to load model!')
    input('Press Enter...')
"
pause
