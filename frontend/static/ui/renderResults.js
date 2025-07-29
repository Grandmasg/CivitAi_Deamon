// Model results rendering logic for CivitAI frontend
// Handles rendering of model cards and error/loading states

window.renderResults = function(state, flattenModels, escapeHtml, modelManager) {
  if (state.loading) return '<div>🔄 Loading...</div>';
  if (state.error) {
    let reloadBtn = '';
    if (state.error === 'Failed to fetch results.' || /API error/i.test(state.error)) {
      reloadBtn = `<button class="btn btn-outline-danger btn-sm ms-2" id="reloadApiBtn">Reload</button>`;
    }
    setTimeout(() => {
      const btn = document.getElementById('reloadApiBtn');
      if (btn) {
        btn.onclick = function() {
          window.fetchResults();
        };
      }
    }, 0);
    return `<div class="alert alert-danger d-flex align-items-center justify-content-between">${escapeHtml(state.error)}${reloadBtn}</div>`;
  }

  const filtered = flattenModels(state.result)
    .filter(r => !state.filters.type || r.type === state.filters.type);

  if (!filtered.length) return `<div class="alert alert-warning text-center">No results found.</div>`;

  const template = Handlebars.compile(document.getElementById('model-card-template').innerHTML);

  const jwtReady = !!(modelManager && modelManager.config && modelManager.config.jwt_secret);
  const cards = filtered.map(r => {
    // Main image or video and gallery
    let mainMedia = r.image || (r.images && r.images[0]?.url) || 'https://placehold.co/400x400?text=Model+Preview';
    let gallery = Array.isArray(r.images) ? r.images.map(img => img.url) : [];
    let isVideo = typeof mainMedia === 'string' && mainMedia.match(/\.mp4($|\?)/i);

    // Creator info
    let creator = r.creator || {};
    let creatorName = creator.username || 'Unknown';
    let creatorAvatar = creator.image || '';

    // Model info
    let id = r.id;
    let title = escapeHtml(r.modelName || r.name || 'Untitled'); // always use parent model name
    let type = r.type ? escapeHtml(r.type.replace(/[^\w\s-]/g, '')) : 'Unknown';
    let description = r.description ? escapeHtml(r.description.replace(/<[^>]+>/g, '').slice(0, 220)) : '';
    let descriptionMore = r.description && r.description.length > 220;

    // Stats
    let stats = r.stats || {};
    let statsHtml = `<div class="row g-1 mb-2">
      <div class="col-auto"><span class="badge bg-light text-dark"><b>👍</b> ${stats.thumbsUpCount ?? '-'}</span></div>
      <div class="col-auto"><span class="badge bg-light text-dark"><b>👎</b> ${stats.thumbsDownCount ?? '-'}</span></div>
      <div class="col-auto"><span class="badge bg-light text-dark"><b>⬇️</b> ${stats.downloadCount ?? '-'}</span></div>
      <div class="col-auto"><span class="badge bg-light text-dark"><b>💬</b> ${stats.commentCount ?? '-'}</span></div>
    </div>`;

    // Tags
    let tags = Array.isArray(r.tags) ? r.tags : [];

    // Version info
    let baseModel = ''; // Initialize baseModel here
    let subtitle = '';
    let olderVersions = [];
    let sha256 = '';
    if (Array.isArray(r.modelVersions) && r.modelVersions.length > 0) {
      if (r.modelVersions[0].name && r.modelVersions[0].name !== r.modelName) {
        subtitle = escapeHtml(r.modelVersions[0].name);
        baseModel = r.modelVersions[0].baseModel || '';
      }
      // Always try to extract sha256 from files[0].hashes.SHA256 if available
      if (Array.isArray(r.modelVersions[0].files) && r.modelVersions[0].files.length > 0 && r.modelVersions[0].files[0].hashes && r.modelVersions[0].files[0].hashes.SHA256) {
        sha256 = r.modelVersions[0].files[0].hashes.SHA256;
      }
      if (r.modelVersions.length > 1) {
        olderVersions = r.modelVersions.slice(1).map(v => ({
          id: v.id,
          name: v.name,
          baseModel: v.baseModel,
          publishedAt: v.publishedAt,
          nsfwLevel: v.nsfwLevel,
          availability: v.availability,
          downloadUrl: v.downloadUrl,
          stats: v.stats || {},
          images: Array.isArray(v.images) ? v.images.map(img => img.url) : []
        }));
      }
    }

    // Download button logic (same as before)
    let availability = (r.raw?.modelVersions?.[0]?.availability) || r.modelVersions?.[0]?.availability || r.availability || '';
    let btnText = 'Download';
    let btnDisabled = '';
    let disabled = '';
    let btnClass = 'btn btn-sm btn-primary';
    if (availability === 'EarlyAccess') {
      btnText = 'EarlyAccess';
      btnDisabled = 'disabled';
      disabled = 'disabled';
      btnClass = 'btn btn-warning btn-sm';
    } else if (r.isDownloaded || state.downloadStatus[r.id] === 'downloaded') {
      btnText = 'Downloaded';
      btnDisabled = 'disabled';
      disabled = 'disabled';
      btnClass = 'btn btn-success btn-sm';
    } else if (state.downloadStatus[r.id] === 'downloading') {
      if (!(r.isDownloaded || state.downloadStatus[r.id] === 'downloaded')) {
        btnText = 'Downloading..';
        btnDisabled = 'disabled';
        disabled = 'disabled';
        btnClass = 'btn btn-info btn-sm';
      } else {
        btnText = 'Downloaded';
        btnDisabled = 'disabled';
        disabled = 'disabled';
        btnClass = 'btn btn-success btn-sm';
      }
    } else if (state.downloadStatus[r.id] === 'in_queue') {
      if (!(r.isDownloaded || state.downloadStatus[r.id] === 'downloaded')) {
        btnText = 'In queue..';
        btnDisabled = 'disabled';
        disabled = 'disabled';
        btnClass = 'btn btn-secondary btn-sm';
      } else {
        btnText = 'Downloaded';
        btnDisabled = 'disabled';
        disabled = 'disabled';
        btnClass = 'btn btn-success btn-sm';
      }
    } else if (!jwtReady && state.loading) {
      btnText = 'Loading...';
      btnDisabled = 'disabled';
      disabled = 'disabled';
      btnClass = 'btn btn-secondary btn-sm';
    }
    const civitaiUrl = r.civitaiUrl || (r.id ? `https://civitai.com/models/${r.id}` : null);
    const btnClassWithDownload = btnClass + ' download-btn';

    // Pass all fields to template
    return template({
      id,
      mainMedia,
      isVideo,
      gallery,
      creatorName,
      creatorAvatar,
      type,
      baseModel,
      title,
      subtitle,
      description,
      descriptionMore,
      statsHtml,
      batchMode: state.batchMode,
      btnText,
      btnDisabled,
      disabled,
      btnClass: btnClassWithDownload,
      civitaiUrl,
      isDownloaded: r.isDownloaded,
      sha256,
      tags
    });
  }).join('');

  return `${cards}`;
}
