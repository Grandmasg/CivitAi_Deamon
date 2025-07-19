// Helper: check if current user is admin (JWT role)
function isAdmin() {
    if (!jwtToken) return false;
    try {
        const payload = JSON.parse(atob(jwtToken.split('.')[1]));
        return payload.role === 'admin';
    } catch {
        return false;
    }
}

function updateAdminControls() {
    const adminControls = document.getElementById('admin-controls');
    if (isAdmin()) {
        adminControls.style.display = '';
    } else {
        adminControls.style.display = 'none';
    }
}

let ws;
let jwtToken = localStorage.getItem('jwtToken') || '';

function updateStatus() {
    if (!jwtToken) return;
    fetch('/api/status', {
        headers: { 'Authorization': 'Bearer ' + jwtToken }
    })
    .then(resp => resp.json())
    .then(data => {
        document.getElementById('daemon-status').textContent = data.running ? (data.paused ? 'Paused' : 'Running') : 'Stopped';
    });
}

function updateQueue() {
    if (!jwtToken) return;
    fetch('/api/queue', {
        headers: { 'Authorization': 'Bearer ' + jwtToken }
    })
    .then(resp => resp.json())
    .then(data => {
        const list = document.getElementById('queue-list');
        list.innerHTML = '';
        (data.queue || []).forEach(item => {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            // Toon model_id, filename, status indien beschikbaar
            let text = '';
            if (item.model_id || item.modelId) text += 'ID: ' + (item.model_id || item.modelId) + ' ';
            if (item.filename) text += item.filename + ' ';
            if (item.status) text += '(' + item.status + ')';
            if (!text) text = JSON.stringify(item);
            li.textContent = text;
            list.appendChild(li);
        });
    });
}

function updateCompleted() {
    if (!jwtToken) return;
    fetch('/api/completed', {
        headers: { 'Authorization': 'Bearer ' + jwtToken }
    })
    .then(resp => resp.json())
    .then(data => {
        const list = document.getElementById('completed-list');
        list.innerHTML = '';
        (data.completed || []).forEach(item => {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.textContent = item.filename || JSON.stringify(item);
            list.appendChild(li);
        });
    });
}

function updateMetrics() {
    if (!jwtToken) return;
    fetch('/api/metrics', {
        headers: { 'Authorization': 'Bearer ' + jwtToken }
    })
    .then(resp => resp.json())
    .then(data => {
        document.getElementById('metrics').textContent = JSON.stringify(data, null, 2);
    });
}

function connectWebSocket() {
    if (!jwtToken) return;
    ws = new WebSocket(`ws://${window.location.host}/ws/downloads?token=${jwtToken}`);
    ws.onopen = () => console.log('WebSocket connected');
    ws.onmessage = (event) => {
        // Refresh alles bij event
        updateStatus();
        updateCompleted();
        updateMetrics();
        updateQueue();
    };
    ws.onclose = () => console.log('WebSocket closed');
}

document.getElementById('refresh-status').onclick = function() {
    updateStatus();
    updateCompleted();
    updateMetrics();
    updateQueue();
};

// Login form logic
window.login = async function login(username, role) {
    const resp = await fetch('/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, role })
    });
    const data = await resp.json();
    if (data.access_token) {
        jwtToken = data.access_token;
        localStorage.setItem('jwtToken', jwtToken);
        connectWebSocket();
        updateStatus();
        updateCompleted();
        updateMetrics();
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('logout-btn').style.display = '';
        updateAdminControls();
    }
};

window.logout = function() {
    jwtToken = '';
    localStorage.removeItem('jwtToken');
    if (ws) ws.close();
    document.getElementById('login-form').style.display = '';
    document.getElementById('logout-btn').style.display = 'none';
    updateAdminControls();
};

// On load
if (jwtToken) {
    connectWebSocket();
    updateStatus();
    updateCompleted();
    updateMetrics();
    updateQueue();
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('logout-btn').style.display = '';
    updateAdminControls();
} else {
    document.getElementById('login-form').style.display = '';
    document.getElementById('logout-btn').style.display = 'none';
    updateAdminControls();
}

// Admin button actions
document.addEventListener('DOMContentLoaded', function() {
    const pauseBtn = document.getElementById('pause-btn');
    const resumeBtn = document.getElementById('resume-btn');
    const stopBtn = document.getElementById('stop-btn');
    if (pauseBtn) pauseBtn.onclick = function() { adminAction('/api/pause'); };
    if (resumeBtn) resumeBtn.onclick = function() { adminAction('/api/resume'); };
    if (stopBtn) stopBtn.onclick = function() { adminAction('/api/stop'); };
});

function adminAction(url) {
    if (!jwtToken) return;
    fetch(url, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + jwtToken }
    })
    .then(resp => resp.json())
    .then(data => {
        updateStatus();
    });
}
