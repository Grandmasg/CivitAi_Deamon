
# 🧭 TODO-frontend.txt — CivitAI Daemon Search Frontend (v3 - API-native & interactive)

────────────────────────────
🧠 Structure & Routing
────────────────────────────
[ ] Project folder: frontend/search_gui/
[ ] File structure:
      - templates/search.html
      - static/search.js
      - routes/search.py
[ ] FastAPI GUI route: /gui/search
[ ] Backend API-proxy: /api/search → fetches data via CivitAI API

────────────────────────────
🔍 API-compatible filters (no query by default)
────────────────────────────
[ ] Form only uses reliable filters:
      - tag=anime / realistic / fantasy / sdxl
      - types=Checkpoint / LoRA / TI
      - period=Week / Month / AllTime
      - sort=MostDownloaded / HighestRated
      - limit=12 / 24 / 36 / 48 / 96
      - nsfw=true (admin only)
      → Do not use query as primary filter

[ ] Tooltip at search field: “Use tags for best results. Search term is optional.”

────────────────────────────
📄 UI Template (search.html)
────────────────────────────
[ ] Search filters:
      - Dropdowns for tag, type, period, sort, limit
      - NSFW toggle (only if user.isAdminNSFWEnabled)

[ ] Smart add-buttons:
      - Example: “➕ Add Top SDXL LoRAs”
      - Automatically performs a call like:
        GET /models?tag=sdxl&types=LoRA&sort=HighestRated&period=Week&limit=8
      - Automatically generates manifest entries

────────────────────────────
📄 Result display
────────────────────────────
[ ] 3-column grid (responsive):
      - Name, model_type, version ID
      - Creator, filesize, publish date
      - Preview (image / video / fallback)
          - images[0] → fallback images[1] → /static/default_preview.png
          - Detect .mp4/.webm → show <video autoplay muted>
      - Checkbox → add to manifest
      - Clickable card opens detail overlay

────────────────────────────
📋 Detail overlay (no extra API call)
────────────────────────────
[ ] From original `/models` response:
      - Show: tags, description, creator, publish date
      - modelVersions[]:
          - Name, version ID
          - Files[].name / downloadUrl / sha256 / sizeKB
      - Download per version possible
      - Layout: modal overlay with scrollable content and close button

────────────────────────────
🔔 UI-feedback: Download-status en alerts
────────────────────────────

[ ] Alert bij selectie/verzenden:
    - “Download gestart voor 5 modellen”
    - Tijdelijk bovenaan weergegeven (3–5 sec) met fade-out
    - Type: info-alert (blauw)

[ ] Succesalert:
    - Per model: “Model ‘Karinn’ succesvol gedownload”
    - Groene badge of alertbox naast de kaart
    - Optioneel totaaloverzicht: “✅ 5 modellen succesvol”

[ ] Foutmelding:
    - “❌ Download mislukt voor model ‘XYZ’ — probeer opnieuw”
    - Tooltip of expandable foutdetails
    - Type: rode alert met retry-optie

────────────────────────────
📥 Downloadvoortgang + hashcontrole
────────────────────────────


[ ] Button: “📊 View Progress” in GUI
    - Opens modal or tab with progress list

[ ] Per model entry:
    - Name + status:
        - ⏳ “Downloading (40%)”
        - ✅ “Download complete”
        - 🔍 “SHA256 verification in progress”
        - ❌ “SHA256 mismatch — download cancelled”

[ ] Optionally: log line or timestamp per status
    - “Verified at 12:43:21”

[ ] Optional: loading bar per model
    - Simulate via timer or real-time via websocket/logparser

[ ] After all are finished:
    - “📁 All selected models have been processed”
    - Hide progress tab automatically (configurable)

────────────────────────────
📥 Download button: status + disabling
────────────────────────────

[ ] Check if model is already downloaded:
      - Compare against local database or list from daemon
      - GET /api/downloaded_versions
        → [987654, 888888, 777777, ...]  // list of modelVersionIds that are already downloaded

[ ] Frontend behavior per model card:

      - If model is already downloaded:
          [ ] Hide checkbox
          [ ] Show button: “✅ Downloaded”
                - Disabled
                - Grey style (cursor: not-allowed)
                - Tooltip: “Model is already present”

      - If model is not yet downloaded:
          [ ] Show active button: “📦 Add to manifest”

[ ] Write download status in manifest overlay and progress tab
      - “Status: Already present” or “✅ Ready in local cache”

[ ] Optional: add filter → “Hide already downloaded models”
      - Checkbox above search results
      - Example: ?excludeDownloaded=true → backend fetches list, filters

────────────────────────────
📦 Manifest submission
────────────────────────────
[ ] JS builds:
    {
      "manifest": [
        {
          modelId,
          modelVersionId,
          model_type,
          sha256,
          url,
          filename,
          priority
        }
      ]
    }

[ ] Send to: POST /api/download-manifest
[ ] Feedback per entry: ✅ / ❌
[ ] Hide send button if 0 selected
[ ] Optional preview modal of full manifest

────────────────────────────
🔞 NSFW handling
────────────────────────────
[ ] If nsfw_level > 4 and user is not admin:
      - Show overlay mask over preview
      - Text: “NSFW content shielded”
      - Tooltip + lock icon
[ ] Admin sees full model

────────────────────────────
▶ Cursor-based pagination (forward only)
────────────────────────────
[ ] Use metadata.nextCursor → “▶ Next Page” button
      - Only show if present
      - Fetch with: /models?cursor={nextCursor}&limit=...
      - Append or overwrite (depending on mode)
      - Smooth scroll after loading

[ ] No previous button, no page numbers

────────────────────────────
🎨 UX & Validation
────────────────────────────
[ ] Spinner during fetch
[ ] Error handling for API errors
[ ] Responsive layout for mobile
[ ] Checkbox highlight
[ ] Tooltip at filters
[ ] Fallback preview if image is missing

────────────────────────────
🧩 Optional extensions (API-compatible)
────────────────────────────
[ ] Manifest preview before sending
[ ] Favorites via localStorage
[ ] Show search history
[ ] Theme toggle (light/dark)
[ ] Suggestions via tag-pills
[ ] Accessibility (a11y): keyboard navigation, ARIA labels
[ ] i18n/language toggle (multi-language support)
[ ] Rate limiting or debounce for API calls
[ ] API error logging/reporting (debugging)
[ ] User feedback for slow/empty results (e.g. “No models found”)

────────────────────────────
🧪 Test scenarios
────────────────────────────
[ ] Test filter: tag=sdxl, types=LoRA, sort=HighestRated
[ ] Click smart add-button → manifest filled
[ ] Click card → overlay shows versions + metadata
[ ] NSFW as guest → preview masked
[ ] Send manifest with 5 selected models
[ ] Cursor pagination: scroll through multiple pages

────────────────────────────
✅ Launch
────────────────────────────
[ ] Add todo_frontend.txt to repo root
[ ] Commit + push search_gui folder + routes
[ ] Document manifest format, filter logic & API structure in README.md