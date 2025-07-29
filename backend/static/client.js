// Call all update functions in one go
function updateAll() {
    updateStatus();
    updateMetrics();
    updateQueueAndActive();
}

// Combined function to fetch both queue and last_downloaded in one tick
function updateQueueAndActive() {
    if (!jwtToken) return;
    Promise.all([
        fetch('/api/queue', {
            headers: { 'Authorization': 'Bearer ' + jwtToken }
        }).then(resp => resp.json()),
        fetch('/api/last_downloaded', {
            headers: { 'Authorization': 'Bearer ' + jwtToken }
        }).then(resp => resp.json())
    ]).then(([queueData, lastData]) => {
        // Update queue (show all items)
        const queueList = document.getElementById('queue-list');
        queueList.innerHTML = '';
        const items = queueData.queue || [];
        if (items.length === 0 || (items.length === 1 && typeof items[0] === 'string')) {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.textContent = 'Queue is empty.';
            queueList.appendChild(li);
        } else {
            items.forEach(item => {
                const li = document.createElement('li');
                li.className = 'list-group-item';
                let text = '';
                // Always show model_id
                text += 'ID: ' + (item.model_id || item.modelId || '-') + ' - ';
                text += 'Version ID: ' + (item.model_version_id || item.modelVersionId || '-') + ' - ';
                if (item.filename) text += item.filename + ' - ';
                if (item.model_type) text += '[' + item.model_type + '] ';
                li.textContent = text.trim();
                queueList.appendChild(li);
            });
        }
        // Update active download (show only first item in queue)
        const activeList = document.getElementById('active-downloads-list');
        activeList.innerHTML = '';
        if (items.length === 0 || (items.length === 1 && typeof items[0] === 'string')) {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.textContent = 'No active downloads.';
            activeList.appendChild(li);
        } else {
            const item = items[0];
            const li = document.createElement('li');
            li.className = 'list-group-item';
            let text = '';
            // Always show model_id
            text += 'ID: ' + (item.model_id || item.modelId || '-') + ' - ';
            text += 'Version ID: ' + (item.model_version_id || item.modelVersionId || '-') + ' - ';
            if (item.filename) text += item.filename + ' - ';
            if (item.model_type) text += '[' + item.model_type + '] ';
            li.textContent = text.trim();
            activeList.appendChild(li);
        }
        // Update last downloaded
        const lastList = document.getElementById('last-downloaded-list');
        lastList.innerHTML = '';
        const lastItems = lastData.last_downloaded || [];
        if (lastItems.length === 0) {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.textContent = 'No downloads completed yet.';
            lastList.appendChild(li);
        } else {
            lastItems.forEach(item => {
                const li = document.createElement('li');
                li.className = 'list-group-item';
                let text = '';
                if (item.model_id) text += 'ID: ' + item.model_id + ' ';
                if (item.filename) text += item.filename + ' ';
                if (item.file_size) text += '(' + item.file_size + ' bytes) ';
                if (item.download_time) text += '[' + item.download_time + 's] ';
                if (item.model_type) text += '[' + item.model_type + '] ';
                li.textContent = text.trim();
                lastList.appendChild(li);
            });
        }
    });
}

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

// Helper: update admin controls visibility based on JWT role
function updateAdminControls() {
    const adminControls = document.getElementById('admin-controls');
    if (isAdmin()) {
        adminControls.style.display = '';
    } else {
        adminControls.style.display = 'none';
    }
}

// Helper: show alert message
let ws = null;
window._downloadPoller = null;
window._pollerSetCount = 0;
let jwtToken = localStorage.getItem('jwtToken') || '';

// Helper: update status
function updateStatus() {
    if (!jwtToken) return;
    // console.log('DEBUG: updateStatus called', new Date().toISOString(), (new Error()).stack.split('\n')[2]);
    fetch('/api/status', {
        headers: { 'Authorization': 'Bearer ' + jwtToken }
    })
    .then(resp => resp.json())
    .then(data => {
        document.getElementById('daemon-status').textContent = data.running ? (data.paused ? 'Paused' : 'Running') : 'Stopped';
    });
}

// updateQueue is now handled by updateQueueAndActive
function updateMetrics() {
    if (!jwtToken) return;
    // console.log('DEBUG: updateMetrics called', new Date().toISOString(), (new Error()).stack.split('\n')[2]);
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

        // Unieke downloads/fails + totaal
        let uniquesDiv = document.getElementById('metrics-uniques');
        if (!uniquesDiv) {
            uniquesDiv = document.createElement('div');
            uniquesDiv.id = 'metrics-uniques';
            const metricsTables = document.getElementById('metrics-tables');
            if (metricsTables) metricsTables.parentNode.insertBefore(uniquesDiv, metricsTables);
        }
        if (uniquesDiv) {
            uniquesDiv.innerHTML = `
                <b>Totaal unieke downloads:</b> ${data.unique_successful_downloads || 0}
                &nbsp;|&nbsp;
                <b>Totaal unieke fails:</b> ${data.unique_failed_downloads || 0}
                &nbsp;|&nbsp;
                <b>Totaal aantal pogingen:</b> ${data.total_downloads || 0}
            `;
        }

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

// Helper: show progress bar for downloads
function connectWebSocket() {
    if (!jwtToken) return;
    // console.log('DEBUG: updateQueue called', new Date().toISOString(), (new Error()).stack.split('\n')[2]);
    // Always close previous WebSocket and clear poller before opening a new one
    if (ws) {
        ws.close();
        ws = null;
    }
    if (window._downloadPoller) {
        clearInterval(window._downloadPoller);
        window._downloadPoller = null;
    }
    ws = new WebSocket(`ws://${window.location.host}/ws/downloads?token=${jwtToken}`);
    ws.onopen = () => {
        console.log('WebSocket connected');
        window._pollerSetCount = (window._pollerSetCount || 0) + 1;
        window._downloadPoller = setInterval(() => {
            if (!window._pollTick) window._pollTick = 0;
            window._pollTick++;
            // console.log('DEBUG: Poller tick', window._pollTick, 'at', new Date().toISOString());
            updateAll();
        }, 2000);
        // console.log('DEBUG: Polling interval set to 5000ms', window._downloadPoller, 'set count:', window._pollerSetCount);
    };
    ws.onmessage = (event) => {
        // Log the message for debugging
        // console.log('DEBUG: ws.onmessage received', JSON.stringify(event.data), new Date().toISOString());
        let shouldUpdate = false;
        if (event.data && typeof event.data === 'string') {
            try {
                const msg = JSON.parse(event.data);
                // List of events that should trigger a UI update
                const updateEvents = [
                    'queue_changed',
                    'download_started',
                    'download_finished',
                    'download_failed',
                    'metrics_changed',
                    'status_changed'
                ];
                if (msg && msg.event && updateEvents.includes(msg.event)) {
                    shouldUpdate = true;
                }
            } catch (e) {
                // Not JSON, fallback to previous logic
                if (event.data.trim() !== '' && event.data !== 'heartbeat') {
                    shouldUpdate = true;
                }
            }
        }
        if (shouldUpdate) {
            updateStatus();
            updateMetrics();
            updateLastDownloaded();
        }
    };
    ws.onclose = () => {
        console.log('WebSocket closed');
        if (window._downloadPoller) {
            clearInterval(window._downloadPoller);
            window._downloadPoller = null;
        }
    };
}

// Call all update functions in one go
document.getElementById('refresh-status').onclick = function() {
    updateStatus();
    updateMetrics();
    updateQueueAndActive();
    updateLastDownloaded();
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
        // Do NOT call updateStatus/updateMetrics here, let the poller and WebSocket handle updates
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('logout-btn').style.display = '';
        updateAdminControls();
    }
};

// Logout logic
window.logout = function() {
    jwtToken = '';
    localStorage.removeItem('jwtToken');
    if (ws) {
        ws.close();
        ws = null;
    }
    if (window._downloadPoller) {
        clearInterval(window._downloadPoller);
        window._downloadPoller = null;
    }
    document.getElementById('login-form').style.display = '';
    document.getElementById('logout-btn').style.display = 'none';
    updateAdminControls();
};

// On load, alles pas na DOMContentLoaded
function updateLastDownloaded() {
    if (!jwtToken) return;
    fetch('/api/last_downloaded', {
        headers: { 'Authorization': 'Bearer ' + jwtToken }
    })
    .then(resp => resp.json())
    .then(data => {
        const list = document.getElementById('last-downloaded-list');
        list.innerHTML = '';
        const items = data.last_downloaded || [];
        if (items.length === 0) {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.textContent = 'No downloads completed yet.';
            list.appendChild(li);
            return;
        }
        items.forEach(item => {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            let text = '';
            if (item.model_id) text += 'ID: ' + item.model_id + ' ';
            if (item.filename) text += item.filename + ' ';
            if (item.file_size) text += '(' + item.file_size + ' bytes) ';
            if (item.download_time) text += '[' + item.download_time + 's] ';
            if (item.model_type) text += '[' + item.model_type + '] ';
            li.textContent = text.trim();
            list.appendChild(li);
        });
    });
}

// Initialize WebSocket and update functions on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    if (jwtToken) {
        connectWebSocket();
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('logout-btn').style.display = '';
        updateAdminControls();
        // Do NOT call any update functions here; only connectWebSocket
    } else {
        document.getElementById('login-form').style.display = '';
        document.getElementById('logout-btn').style.display = 'none';
        updateAdminControls();
        if (window._downloadPoller) clearInterval(window._downloadPoller);
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

// Helper: perform admin action (pause/resume/stop)
function adminAction(url) {
    if (!jwtToken) return;
    // console.log('DEBUG: updateLastDownloaded called', new Date().toISOString(), (new Error()).stack.split('\n')[2]);
    fetch(url, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + jwtToken }
    })
    .then(resp => resp.json())
    .then(data => {
        updateStatus();
    });
}
