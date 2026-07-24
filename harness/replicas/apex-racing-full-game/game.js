(function() {
    const canvas = document.getElementById('game-canvas');
    const ctx = canvas.getContext('2d');
    const minimapCanvas = document.getElementById('minimap-canvas');
    const minimapCtx = minimapCanvas.getContext('2d');
    let gameState = 'menu';
    let animationId = null;
    let startTime = 0;
    let currentTime = 0;
    let lapCount = 1;
    const totalLaps = 3;
    let position = 1;
    let currentCheckpoint = 0;
    const checkpoints = [
        { x: 150, y: 100, name: 'Turn 1' },
        { x: 350, y: 50, name: 'Turn 2' },
        { x: 450, y: 200, name: 'Turn 3' },
        { x: 400, y: 350, name: 'Turn 4' },
        { x: 200, y: 400, name: 'Turn 5' },
        { x: 100, y: 250, name: 'Finish' },
    ];
    const trackPoints = [
        { x: 100, y: 200 },
        { x: 150, y: 100 },
        { x: 350, y: 50 },
        { x: 450, y: 200 },
        { x: 400, y: 350 },
        { x: 200, y: 400 },
        { x: 100, y: 250 },
        { x: 100, y: 200 },
    ];
    const car = {
        x: 100,
        y: 200,
        angle: -Math.PI / 2,
        speed: 0,
        maxSpeed: 300,
        acceleration: 5,
        deceleration: 0.95,
        steering: 0,
        handling: 0.8,
        brake: 0,
        gear: 1,
        gears: [0, 30, 60, 100, 150, 200, 250, 300],
    };
    const keys = {
        up: false,
        down: false,
        left: false,
        right: false,
        space: false,
    };
    let cameraMode = 0;
    const cameraModes = ['rear', 'front', 'top'];
    const leaderboard = [
        { name: 'SpeedDemon_99', time: '01:23.456' },
        { name: 'RacingPro_X', time: '01:25.789' },
        { name: 'TurboCharged', time: '01:27.123' },
        { name: 'FormulaOne', time: '01:28.456' },
        { name: 'DriftKing', time: '01:29.789' },
        { name: 'FastLane', time: '01:31.234' },
        { name: 'RaceMaster', time: '01:32.567' },
        { name: 'SpeedRacer', time: '01:33.890' },
    ];
    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    function init() {
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);
        window.addEventListener('keydown', handleKeyDown);
        window.addEventListener('keyup', handleKeyUp);
        initMobileControls();
        startLoading();
    }
    function startLoading() {
        const loadingScreen = document.getElementById('loading-screen');
        const progress = document.querySelector('.loading-progress');
        const mainMenu = document.getElementById('main-menu');
        
        let progressWidth = 0;
        const interval = setInterval(() => {
            progressWidth += Math.random() * 15;
            if (progressWidth >= 100) {
                progressWidth = 100;
                clearInterval(interval);
                setTimeout(() => {
                    loadingScreen.style.display = 'none';
                    mainMenu.style.display = 'flex';
                }, 500);
            }
            progress.style.width = progressWidth + '%';
        }, 100);
    }
    function startGame() {
        document.getElementById('main-menu').style.display = 'none';
        document.getElementById('game-container').style.display = 'block';
        gameState = 'playing';
        startTime = Date.now();
        resetCar();
        gameLoop();
    }
    function resumeGame() {
        document.getElementById('pause-menu').classList.add('hidden');
        gameState = 'playing';
        startTime = Date.now() - currentTime;
        gameLoop();
    }
    function restartGame() {
        document.getElementById('pause-menu').classList.add('hidden');
        document.getElementById('race-complete').classList.add('hidden');
        lapCount = 1;
        currentCheckpoint = 0;
        position = 1;
        startGame();
    }
    function quitToMenu() {
        gameState = 'menu';
        document.getElementById('game-container').style.display = 'none';
        document.getElementById('pause-menu').classList.add('hidden');
        document.getElementById('race-complete').classList.add('hidden');
        document.getElementById('main-menu').style.display = 'flex';
        if (animationId) {
            cancelAnimationFrame(animationId);
        }
    }
    function resetCar() {
        car.x = 100;
        car.y = 200;
        car.angle = -Math.PI / 2;
        car.speed = 0;
        car.gear = 1;
        car.steering = 0;
        car.brake = 0;
    }
    function handleKeyDown(e) {
        switch(e.code) {
            case 'KeyW':
            case 'ArrowUp':
                keys.up = true;
                break;
            case 'KeyS':
            case 'ArrowDown':
                keys.down = true;
                break;
            case 'KeyA':
            case 'ArrowLeft':
                keys.left = true;
                break;
            case 'KeyD':
            case 'ArrowRight':
                keys.right = true;
                break;
            case 'Space':
                keys.space = true;
                e.preventDefault();
                break;
            case 'Escape':
                if (gameState === 'playing') {
                    pauseGame();
                }
                break;
            case 'KeyC':
                cameraMode = (cameraMode + 1) % cameraModes.length;
                break;
            case 'KeyR':
                if (gameState === 'playing') {
                    restartGame();
                }
                break;
        }
    }
    function handleKeyUp(e) {
        switch(e.code) {
            case 'KeyW':
            case 'ArrowUp':
                keys.up = false;
                break;
            case 'KeyS':
            case 'ArrowDown':
                keys.down = false;
                break;
            case 'KeyA':
            case 'ArrowLeft':
                keys.left = false;
                break;
            case 'KeyD':
            case 'ArrowRight':
                keys.right = false;
                break;
            case 'Space':
                keys.space = false;
                break;
        }
    }
    function initMobileControls() {
        const steeringWheel = document.getElementById('steering-wheel');
        const accelBtn = document.getElementById('accel-btn');
        const brakeBtn = document.getElementById('brake-btn');
        
        let wheelCenterX = 0;
        let wheelCenterY = 0;
        
        steeringWheel.addEventListener('touchstart', (e) => {
            const rect = steeringWheel.getBoundingClientRect();
            wheelCenterX = rect.left + rect.width / 2;
            wheelCenterY = rect.top + rect.height / 2;
            handleSteering(e.touches[0]);
        });
        
        steeringWheel.addEventListener('touchmove', (e) => {
            e.preventDefault();
            handleSteering(e.touches[0]);
        });
        
        steeringWheel.addEventListener('touchend', () => {
            car.steering = 0;
        });
        
        accelBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            keys.up = true;
        });
        
        accelBtn.addEventListener('touchend', () => {
            keys.up = false;
        });
        
        brakeBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            keys.down = true;
        });
        
        brakeBtn.addEventListener('touchend', () => {
            keys.down = false;
        });
        
        function handleSteering(touch) {
            const dx = touch.clientX - wheelCenterX;
            const dy = touch.clientY - wheelCenterY;
            car.steering = Math.max(-1, Math.min(1, dx / 60));
        }
    }
    function updateCar() {
        if (keys.up) {
            car.speed = Math.min(car.speed + car.acceleration, car.maxSpeed);
        } else if (keys.down) {
            car.speed = Math.max(car.speed - car.acceleration * 2, -car.maxSpeed / 2);
        } else {
            car.speed *= car.deceleration;
            if (Math.abs(car.speed) < 0.1) car.speed = 0;
        }
        if (keys.left) {
            car.steering = -1;
        } else if (keys.right) {
            car.steering = 1;
        } else {
            car.steering *= 0.8;
        }
        if (car.speed !== 0) {
            const turnSpeed = (car.speed / car.maxSpeed) * car.steering * 0.1;
            car.angle += turnSpeed;
        }
        car.x += Math.cos(car.angle) * car.speed * 0.1;
        car.y += Math.sin(car.angle) * car.speed * 0.1;
        if (car.x < 0) car.x = 0;
        if (car.x > 500) car.x = 500;
        if (car.y < 0) car.y = 0;
        if (car.y > 450) car.y = 450;
        for (let i = 0; i < car.gears.length - 1; i++) {
            if (car.speed >= car.gears[i] && car.speed < car.gears[i + 1]) {
                car.gear = i + 1;
                break;
            }
        }
        checkCheckpoints();
    }
    function checkCheckpoints() {
        const cp = checkpoints[currentCheckpoint];
        const dx = car.x - cp.x;
        const dy = car.y - cp.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 40) {
            currentCheckpoint = (currentCheckpoint + 1) % checkpoints.length;
            if (currentCheckpoint === 0) {
                lapCount++;
                if (lapCount > totalLaps) {
                    finishRace();
                }
            }
        }
    }
    function finishRace() {
        gameState = 'finished';
        const finalTime = formatTime(currentTime);
        document.getElementById('final-time').textContent = finalTime;
        document.getElementById('final-laps').textContent = lapCount - 1;
        document.getElementById('race-complete').classList.remove('hidden');
    }
    function updateHUD() {
        document.getElementById('speed').textContent = Math.round(car.speed);
        document.getElementById('gear').textContent = car.gear.toString();
        document.getElementById('lap').textContent = lapCount + '/' + totalLaps;
        document.getElementById('time').textContent = formatTime(currentTime);
        document.getElementById('position').textContent = position;
        document.getElementById('checkpoint').textContent = 'Next: ' + checkpoints[currentCheckpoint].name;
    }
    function formatTime(ms) {
        const minutes = Math.floor(ms / 60000);
        const seconds = Math.floor((ms % 60000) / 1000);
        const milliseconds = Math.floor(ms % 1000);
        return String(minutes).padStart(2, '0') + ':' + 
               String(seconds).padStart(2, '0') + '.' + 
               String(milliseconds).padStart(3, '0');
    }
    function draw() {
        ctx.fillStyle = '#1a1a2e';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        drawTrack();
        drawCar();
        drawCheckpoints();
        drawMinimap();
    }
    function drawTrack() {
        ctx.strokeStyle = '#3a3a4e';
        ctx.lineWidth = 60;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.beginPath();
        ctx.moveTo(trackPoints[0].x, trackPoints[0].y);
        for (let i = 1; i < trackPoints.length; i++) {
            ctx.lineTo(trackPoints[i].x, trackPoints[i].y);
        }
        ctx.stroke();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 4;
        ctx.setLineDash([20, 20]);
        ctx.stroke();
        ctx.setLineDash([]);
    }
    function drawCar() {
        ctx.save();
        ctx.translate(car.x, car.y);
        ctx.rotate(car.angle);
        ctx.fillStyle = '#ef4444';
        ctx.beginPath();
        ctx.moveTo(20, 0);
        ctx.lineTo(-15, -10);
        ctx.lineTo(-15, 10);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(-5, -6, 4, 0, Math.PI * 2);
        ctx.arc(-5, 6, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }
    function drawCheckpoints() {
        checkpoints.forEach((cp, index) => {
            const isActive = index === currentCheckpoint;
            ctx.fillStyle = isActive ? '#fbbf24' : '#666688';
            ctx.beginPath();
            ctx.arc(cp.x, cp.y, isActive ? 15 : 10, 0, Math.PI * 2);
            ctx.fill();
            if (isActive) {
                ctx.strokeStyle = '#fbbf24';
                ctx.lineWidth = 2;
                ctx.setLineDash([5, 5]);
                ctx.beginPath();
                ctx.arc(cp.x, cp.y, 20, 0, Math.PI * 2);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        });
    }
    function drawMinimap() {
        minimapCtx.fillStyle = '#1a1a2e';
        minimapCtx.fillRect(0, 0, 200, 200);
        minimapCtx.strokeStyle = '#3a3a4e';
        minimapCtx.lineWidth = 8;
        minimapCtx.beginPath();
        minimapCtx.moveTo(trackPoints[0].x * 0.4, trackPoints[0].y * 0.4);
        for (let i = 1; i < trackPoints.length; i++) {
            minimapCtx.lineTo(trackPoints[i].x * 0.4, trackPoints[i].y * 0.4);
        }
        minimapCtx.stroke();
        minimapCtx.fillStyle = '#ef4444';
        minimapCtx.beginPath();
        minimapCtx.arc(car.x * 0.4, car.y * 0.4, 5, 0, Math.PI * 2);
        minimapCtx.fill();
        checkpoints.forEach((cp) => {
            minimapCtx.fillStyle = '#fbbf24';
            minimapCtx.beginPath();
            minimapCtx.arc(cp.x * 0.4, cp.y * 0.4, 3, 0, Math.PI * 2);
            minimapCtx.fill();
        });
    }
    function gameLoop() {
        if (gameState !== 'playing') return;
        currentTime = Date.now() - startTime;
        updateCar();
        updateHUD();
        draw();
        animationId = requestAnimationFrame(gameLoop);
    }
    function pauseGame() {
        gameState = 'paused';
        document.getElementById('pause-menu').classList.remove('hidden');
    }
    function showLeaderboard() {
        const list = document.getElementById('leaderboard-list');
        list.innerHTML = '';
        leaderboard.forEach((entry, index) => {
            const item = document.createElement('div');
            item.className = 'leaderboard-item' + (index < 3 ? ' podium-' + (index + 1) : '');
            item.innerHTML = '<span class="lb-rank">' + (index + 1) + '</span>' +
                           '<span class="lb-name">' + entry.name + '</span>' +
                           '<span class="lb-time">' + entry.time + '</span>';
            list.appendChild(item);
        });
        document.getElementById('leaderboard-modal').classList.remove('hidden');
    }
    function hideLeaderboard() {
        document.getElementById('leaderboard-modal').classList.add('hidden');
    }
    function showControls() {
        document.getElementById('controls-modal').classList.remove('hidden');
    }
    function hideControls() {
        document.getElementById('controls-modal').classList.add('hidden');
    }
    function saveScore() {
        const name = document.getElementById('player-name').value.trim() || 'Anonymous';
        const time = document.getElementById('final-time').textContent;
        leaderboard.push({ name: name, time: time });
        leaderboard.sort((a, b) => a.time.localeCompare(b.time));
        leaderboard.pop();
        alert('Score saved! Check the leaderboard.');
        hideLeaderboard();
        showLeaderboard();
    }
    window.startGame = startGame;
    window.resumeGame = resumeGame;
    window.restartGame = restartGame;
    window.quitToMenu = quitToMenu;
    window.showLeaderboard = showLeaderboard;
    window.hideLeaderboard = hideLeaderboard;
    window.showControls = showControls;
    window.hideControls = hideControls;
    window.saveScore = saveScore;
    init();
});