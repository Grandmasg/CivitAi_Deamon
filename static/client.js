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

function updateMetrics() {
    if (!jwtToken) return;
    fetch('/api/metrics', {
        headers: { 'Authorization': 'Bearer ' + jwtToken }
    })
    .then(resp => resp.json())
    .then(data => {
        // Per dag, type, status
        const tbody1 = document.querySelector('#metrics-per-day-type-status tbody');
        if (!tbody1) {
            console.error('metrics-per-day-type-status tbody not found!');
            return;
        }
        const perDay = data.downloads_per_day_type_status || [];
        tbody1.innerHTML = '';
        if (perDay.length === 0) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 4;
            td.textContent = 'Geen data';
            tr.appendChild(td);
            tbody1.appendChild(tr);
        } else {
            perDay.forEach(row => {
                const tr = document.createElement('tr');
                row.forEach(cell => {
                    const td = document.createElement('td');
                    td.textContent = cell;
                    tr.appendChild(td);
                });
                tbody1.appendChild(tr);
            });
        }

        // File size stats per type
        const tbody2 = document.querySelector('#metrics-file-size tbody');
        if (!tbody2) {
            console.error('metrics-file-size tbody not found!');
            return;
        }
        const fileSize = data.file_size_stats_per_type || [];
        tbody2.innerHTML = '';
        if (fileSize.length === 0) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 5;
            td.textContent = 'Geen data';
            tr.appendChild(td);
            tbody2.appendChild(tr);
        } else {
            fileSize.forEach(row => {
                const tr = document.createElement('tr');
                row.forEach((cell, i) => {
                    const td = document.createElement('td');
                    // Alleen kolommen 1,2,3 (gemiddelde, min, max) krijgen MB, Count (laatste) nooit
                    if ((i === 1 || i === 2 || i === 3) && cell != null) {
                        td.textContent = Math.round(cell/1024/1024) + ' MB';
                    } else if (i === 4) {
                        td.textContent = (typeof cell === 'number' ? Math.round(cell).toString() : cell); // Count: nooit MB, ook niet bij 0
                    } else {
                        td.textContent = cell;
                    }
                    tr.appendChild(td);
                });
                tbody2.appendChild(tr);
            });
        }

        // Download time stats per type
        const tbody3 = document.querySelector('#metrics-download-time tbody');
        if (!tbody3) {
            console.error('metrics-download-time tbody not found!');
            return;
        }
        const dlTime = data.download_time_stats_per_type || [];
        tbody3.innerHTML = '';
        if (dlTime.length === 0) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 5;
            td.textContent = 'Geen data';
            tr.appendChild(td);
            tbody3.appendChild(tr);
        } else {
            dlTime.forEach(row => {
                const tr = document.createElement('tr');
                row.forEach((cell, i) => {
                    const td = document.createElement('td');
                    // Count column is always last (i==row.length-1)
                    if (i === row.length-1 && typeof cell === 'number') {
                        td.textContent = cell.toString();
                    } else if (typeof cell === 'number') {
                        td.textContent = cell.toFixed(2);
                    } else {
                        td.textContent = cell;
                    }
                    tr.appendChild(td);
                });
                tbody3.appendChild(tr);
            });
        }

        // Totaal aantal downloads
        let totalDiv = document.getElementById('metrics-total-downloads');
        if (!totalDiv) {
            totalDiv = document.createElement('div');
            totalDiv.id = 'metrics-total-downloads';
            const metricsTables = document.getElementById('metrics-tables');
            if (metricsTables) metricsTables.prepend(totalDiv);
        }
        if (totalDiv) totalDiv.innerHTML = `<b>Totaal aantal downloads:</b> ${data.total_downloads || 0}`;

        // Optioneel: ruwe JSON tonen voor debug
        const metricsDiv = document.getElementById('metrics');
        if (metricsDiv) metricsDiv.textContent = JSON.stringify(data, null, 2);

        // Forceer een redraw van de metrics-tabel (workaround voor browser caching/DOM update issues)
        const metricsTables = document.getElementById('metrics-tables');
        if (metricsTables) {
            metricsTables.style.display = 'none';
            void metricsTables.offsetHeight; // force reflow
            metricsTables.style.display = '';
        }
    });
}

function connectWebSocket() {
    if (!jwtToken) return;
    ws = new WebSocket(`ws://${window.location.host}/ws/downloads?token=${jwtToken}`);
    ws.onopen = () => console.log('WebSocket connected');
    ws.onmessage = (event) => {
        // Refresh alles bij event
        updateStatus();
        updateMetrics();
        updateQueue();
    };
    ws.onclose = () => console.log('WebSocket closed');
}

document.getElementById('refresh-status').onclick = function() {
    updateStatus();
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
// On load, alles pas na DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    if (jwtToken) {
        connectWebSocket();
        updateStatus();
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
});

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
