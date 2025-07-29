// src/modelManager.js

class ModelManager {
  // Public getter for config so modelManager.config works in frontend
  get config() {
    return this.#state.config;
  }
  #state = {
    filters: {
      type: '',
      nsfw: false,
      period: 'All Time',
      searchTerm: '',
      limit: '24',
      sort: '',
      cursor: null
    },
    tags: '',
    result: [],
    loading: false,
    error: null,
    config: null,
    nextPage: null,
    batchMode: false,
    batchSelected: [],
    downloaded: [],
    inQueue: [],
    downloadStatus: {},
    ws: null,
  };
  #modelProgress = {};
  #configPromise = null;

  #escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  #flattenModels(arr) {
    let out = [];
    for (const item of arr) {
      if (Array.isArray(item)) {
        out = out.concat(this.#flattenModels(item));
      } else if (item && typeof item === 'object') {
        if (typeof item.title === 'string') {
          out.push(item);
        } else {
          for (const v of Object.values(item)) {
            if (Array.isArray(v) || (v && typeof v === 'object')) {
              out = out.concat(this.#flattenModels([v]));
            }
          }
        }
      }
    }
    return out;
  }

  async init() {
    // Wait for config to be loaded and set before resolving
    const config = await this.loadConfig();
    if (!config) throw new Error('Config not loaded');
    await this.setupWebSocket();
    this.render();
    return config;
  }

  async loadConfig() {
    if (this.#state.config) return this.#state.config;
    if (this.#configPromise) return this.#configPromise;
    this.#configPromise = (async () => {
      try {
        const res = await fetch('/configs/config.json');
        if (!res.ok) throw new Error('Config not found');
        const configObj = await res.json();
        this.#state.config = configObj;
        // console.log('[loadConfig] Loaded config:', this.#state.config);
        return this.#state.config;
      } catch (e) {
        this.#state.config = null;
        // console.error('[loadConfig] Error loading config:', e);
        return null;
      } finally {
        // Only clear configPromise after config is set
        this.#configPromise = null;
      }
    })();
    return this.#configPromise;
  }

  async setupWebSocket() {
    if (this.#state.ws) return;
    // WebSocket setup code here
  }

  render() {
    // Call renderFilters, renderResults, etc.
  }

  showAlert(message, type = 'info', timeout = 5000) {
    let container = document.getElementById('alert-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'alert-container';
      container.style.position = 'fixed';
      container.style.top = '20px';
      container.style.right = '20px';
      container.style.zIndex = '9999';
      document.body.appendChild(container);
    }

    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.role = 'alert';
    alert.innerHTML = `
      ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    container.appendChild(alert);

    setTimeout(() => {
      alert.classList.remove('show');
      alert.classList.add('hide');
      setTimeout(() => alert.remove(), 500);
    }, timeout);
  }

  showModelCardProgressBar(modelId, percent, filename, isHashProgress = false) {
    const card = document.querySelector(`.model-card .download-btn[data-model-id='${modelId}']`)?.closest('.model-card');
    if (!card) return;

    let bar = card.querySelector('.model-download-progress');
    if (!bar) {
      bar = document.createElement('div');
      bar.className = 'model-download-progress mt-2';
      bar.innerHTML = `
        <div class="progress" style="height: 24px;">
          <div class="progress-bar progress-bar-striped progress-bar-animated bg-info" role="progressbar" style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
        </div>
        <div class="small" style="margin-top:2px;" id="model-download-label"></div>
      `;
      const btn = card.querySelector('.download-btn[data-model-id]');
      if (btn) btn.parentNode.insertAdjacentElement('afterend', bar);
      else card.appendChild(bar);
    }

    let progressBar = bar.querySelector('.progress-bar');
    let label = bar.querySelector('#model-download-label');
    progressBar.style.width = `${percent}%`;
    progressBar.setAttribute('aria-valuenow', percent);
    label.textContent = `${filename ? filename : ''} (${percent}%)`;

    if (isHashProgress) {
      progressBar.classList.remove('bg-info');
      progressBar.classList.add('bg-warning');
    } else {
      progressBar.classList.remove('bg-warning');
      progressBar.classList.add('bg-info');
    }

    bar.style.display = '';
  }

  hideModelCardProgressBar(modelId) {
    const card = document.querySelector(`.model-card .download-btn[data-model-id='${modelId}']`)?.closest('.model-card');
    if (!card) return;
    const bar = card.querySelector('.model-download-progress');
    if (bar) bar.style.display = 'none';
  }

  toggleBatchSelect(modelId) {
    const idNum = typeof modelId === 'string' ? parseInt(modelId, 10) : modelId;
    const m = this.#state.result.find(x => x && x.id === idNum);
    let modelObj;
    if (m) {
      modelObj = {
        model_id: m.id,
        model_type: m.type,
        model_version_id: m.model_version_id,
        baseModel: m.raw?.modelVersions?.[0]?.baseModel,
        sha256: m.raw?.modelVersions?.[0]?.files?.[0]?.hashes?.SHA256,
        url: m.raw?.modelVersions?.[0]?.files?.[0]?.downloadUrl,
        filename: m.raw?.modelVersions?.[0]?.files?.[0]?.name
      };
    } else {
      modelObj = { model_id: idNum };
    }

    const idx = this.#state.batchSelected.findIndex(sel => (sel.model_id ?? sel) === idNum);
    if (idx === -1) {
      this.#state.batchSelected.push(modelObj);
    } else {
      this.#state.batchSelected.splice(idx, 1);
    }

    try {
      localStorage.setItem('civitai_batch_selected', JSON.stringify(this.#state.batchSelected));
    } catch {}
  }

  // Other methods...
}

window.ModelManager = new ModelManager();
