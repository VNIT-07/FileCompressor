/**
 * FileCompressor - Frontend Application Logic
 * Light, clean, distraction-free interface
 */

document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    systemInfo: null,
    currentFormat: 'zip',
    uploadFormat: 'zip',
    selectedSource: '',
    selectedOutput: '',
    lastResult: null,
    stagedFiles: [],
    history: [],
  };

  // DOM Elements - Navigation
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  const historyCounter = document.getElementById('history-count');

  // DOM Elements - Local Filesystem Tab
  const sourceInput = document.getElementById('local-source-input');
  const outputInput = document.getElementById('local-output-input');
  const btnBrowseFile = document.getElementById('btn-browse-file');
  const btnBrowseFolder = document.getElementById('btn-browse-folder');
  const btnBrowseDest = document.getElementById('btn-browse-dest');
  const sourceInfoBar = document.getElementById('source-info-bar');
  const sourceTypeTag = document.getElementById('source-type-tag');
  const sourceNameDisplay = document.getElementById('source-name-display');
  const sourceSizeDisplay = document.getElementById('source-size-display');
  const formatCards = document.querySelectorAll('.format-card');
  const chkRelative = document.getElementById('chk-relative');
  const chkOverwrite = document.getElementById('chk-overwrite');
  const btnCompressLocal = document.getElementById('btn-compress-local');
  const localStatusText = document.getElementById('local-status-text');
  const localResultCard = document.getElementById('local-result-card');
  const localErrorAlert = document.getElementById('local-error-alert');
  const errorMessage = document.getElementById('error-message');

  // Result Card Elements
  const resultTitleText = document.getElementById('result-title-text');
  const resultTimeText = document.getElementById('result-time-text');
  const resultSavingsPill = document.getElementById('result-savings-pill');
  const statOrigSize = document.getElementById('stat-orig-size');
  const statCompSize = document.getElementById('stat-comp-size');
  const statSavedBytes = document.getElementById('stat-saved-bytes');
  const statFormat = document.getElementById('stat-format');
  const resultOutputPath = document.getElementById('result-output-path');
  const btnRevealFinder = document.getElementById('btn-reveal-finder');
  const btnDownloadResult = document.getElementById('btn-download-result');

  // Quick Chips
  const chipDesktop = document.getElementById('chip-desktop');
  const chipDownloads = document.getElementById('chip-downloads');
  const chipDocuments = document.getElementById('chip-documents');
  const chipCurrent = document.getElementById('chip-current');

  // Size Limit & Optimization Elements
  const chkTargetLimit = document.getElementById('chk-target-limit');
  const targetLabelText = document.getElementById('target-label-text');
  const targetControls = document.getElementById('target-controls');
  const targetSizeInput = document.getElementById('target-size-input');
  const targetPresets = document.querySelectorAll('.target-presets button');
  const chkSplitExceeds = document.getElementById('chk-split-exceeds');
  const chkOptimizeMedia = document.getElementById('chk-optimize-media');
  const chkMaxCompress = document.getElementById('chk-max-compress');
  const chkExcludeJunk = document.getElementById('chk-exclude-junk');

  // Limit Status Banner Elements
  const limitBanner = document.getElementById('limit-banner');
  const limitBannerIcon = document.getElementById('limit-banner-icon');
  const limitBannerTitle = document.getElementById('limit-banner-title');
  const limitBannerDesc = document.getElementById('limit-banner-desc');
  const btnManualSplit = document.getElementById('btn-manual-split');

  // Split Parts Elements
  const splitPartsBox = document.getElementById('split-parts-box');
  const splitCountLabel = document.getElementById('split-count-label');
  const splitPartsList = document.getElementById('split-parts-list');
  const joinCommandCode = document.getElementById('join-command-code');
  const btnCopyJoin = document.getElementById('btn-copy-join');

  // DOM Elements - Upload Tab
  const uploadDropzone = document.getElementById('upload-dropzone');
  const uploadFileInput = document.getElementById('upload-file-input');
  const uploadFolderInput = document.getElementById('upload-folder-input');
  const stagedBox = document.getElementById('staged-box');
  const stagedCountLabel = document.getElementById('staged-count-label');
  const stagedList = document.getElementById('staged-list');
  const btnClearStaged = document.getElementById('btn-clear-staged');
  const uploadPills = document.querySelectorAll('.pill-radio');
  const btnCompressUpload = document.getElementById('btn-compress-upload');
  const uploadStatusText = document.getElementById('upload-status-text');

  // DOM Elements - History Tab
  const historyEmpty = document.getElementById('history-empty');
  const historyList = document.getElementById('history-list');
  const btnRefreshHistory = document.getElementById('btn-refresh-history');

  // DOM Elements - Toast
  const appToast = document.getElementById('app-toast');
  const toastMessage = document.getElementById('toast-message');

  // Toast Helper
  let toastTimer = null;
  function showToast(msg) {
    if (toastTimer) clearTimeout(toastTimer);
    toastMessage.textContent = msg;
    appToast.style.display = 'flex';
    toastTimer = setTimeout(() => {
      appToast.style.display = 'none';
    }, 3200);
  }

  // Helper: Format Bytes
  function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  // 1. Initialize Application
  async function init() {
    try {
      const res = await fetch('/api/info');
      if (res.ok) {
        state.systemInfo = await res.json();
        setupShortcuts();
      }
      fetchHistory();
    } catch (err) {
      console.error('Initialization error:', err);
    }
  }

  // 2. Setup Quick Shortcuts
  function setupShortcuts() {
    if (!state.systemInfo) return;
    const { desktop_dir, downloads_dir, documents_dir, current_dir } = state.systemInfo;

    if (chipDesktop) chipDesktop.addEventListener('click', () => setSourcePath(desktop_dir));
    if (chipDownloads) chipDownloads.addEventListener('click', () => setSourcePath(downloads_dir));
    if (chipDocuments) chipDocuments.addEventListener('click', () => setSourcePath(documents_dir));
    if (chipCurrent) chipCurrent.addEventListener('click', () => setSourcePath(current_dir));
  }

  function setSourcePath(path) {
    sourceInput.value = path;
    checkSourcePath(path);
  }

  // 3. Tab Switching
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab');

      tabBtns.forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      tabContents.forEach(c => {
        c.classList.remove('active');
        c.style.display = 'none';
      });

      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      const targetContent = document.getElementById(targetId);
      if (targetContent) {
        targetContent.classList.add('active');
        targetContent.style.display = 'block';
      }

      if (targetId === 'tab-history') {
        fetchHistory();
      }
    });
  });

  // Native macOS Keyboard Shortcut: Cmd/Ctrl + 1..4 for view switching
  window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && ['1', '2', '3', '4'].includes(e.key)) {
      const idx = parseInt(e.key, 10) - 1;
      if (tabBtns[idx]) {
        e.preventDefault();
        tabBtns[idx].click();
      }
    }
  });

  // 4. Source Path Checking & Auto-Detect
  let checkDebounceTimer = null;
  sourceInput.addEventListener('input', () => {
    clearTimeout(checkDebounceTimer);
    checkDebounceTimer = setTimeout(() => {
      checkSourcePath(sourceInput.value);
    }, 300);
  });

  async function checkSourcePath(path) {
    const trimmed = path.trim();
    if (!trimmed) {
      sourceInfoBar.style.display = 'none';
      return;
    }

    try {
      const res = await fetch('/api/path-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: trimmed }),
      });
      const data = await res.json();

      if (data.exists) {
        sourceTypeTag.textContent = data.is_dir ? 'Folder' : 'File';
        sourceNameDisplay.textContent = data.name;
        sourceSizeDisplay.textContent = data.size_formatted;
        sourceInfoBar.style.display = 'flex';
        localStatusText.textContent = `Ready: ${data.name} (${data.size_formatted})`;
      } else {
        sourceInfoBar.style.display = 'none';
        localStatusText.textContent = 'Path does not exist';
      }
    } catch (err) {
      console.warn('Path check error:', err);
    }
  }

  // 5. Native macOS Picker Integration
  async function triggerBrowse(pickerType, prompt) {
    try {
      showToast('Opening macOS picker dialog...');
      const res = await fetch('/api/browse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: pickerType, prompt: prompt }),
      });
      const data = await res.json();

      if (data.success && data.path) {
        return data.path;
      }
      return null;
    } catch (err) {
      console.error('Browse error:', err);
      return null;
    }
  }

  btnBrowseFile.addEventListener('click', async () => {
    const chosen = await triggerBrowse('file', 'Select a file to compress');
    if (chosen) {
      sourceInput.value = chosen;
      checkSourcePath(chosen);
    }
  });

  btnBrowseFolder.addEventListener('click', async () => {
    const chosen = await triggerBrowse('folder', 'Select a folder to compress');
    if (chosen) {
      sourceInput.value = chosen;
      checkSourcePath(chosen);
    }
  });

  btnBrowseDest.addEventListener('click', async () => {
    const chosen = await triggerBrowse('folder', 'Select destination folder');
    if (chosen) {
      outputInput.value = chosen;
    }
  });

  // 6. Format Card Selection (Local Tab)
  formatCards.forEach(card => {
    card.addEventListener('click', () => {
      formatCards.forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      const radio = card.querySelector('input[type="radio"]');
      radio.checked = true;
      state.currentFormat = radio.value;
    });
  });

  // Target Size Limit Controls
  chkTargetLimit.addEventListener('change', () => {
    targetControls.style.display = chkTargetLimit.checked ? 'block' : 'none';
  });

  targetSizeInput.addEventListener('input', () => {
    const val = targetSizeInput.value.trim();
    targetLabelText.textContent = `${val || '25'} MB`;
    targetPresets.forEach(chip => {
      chip.classList.toggle('active-chip', chip.getAttribute('data-preset') === val);
    });
  });

  targetPresets.forEach(chip => {
    chip.addEventListener('click', () => {
      const preset = chip.getAttribute('data-preset');
      targetSizeInput.value = preset;
      targetLabelText.textContent = `${preset} MB`;
      targetPresets.forEach(c => c.classList.remove('active-chip'));
      chip.classList.add('active-chip');
    });
  });

  // 7. Local Compression Action
  btnCompressLocal.addEventListener('click', async () => {
    const source = sourceInput.value.trim();
    if (!source) {
      showToast('Please specify a source file or folder first.');
      sourceInput.focus();
      return;
    }

    localErrorAlert.style.display = 'none';
    localResultCard.style.display = 'none';
    setCompressingState(true);

    try {
      const payload = {
        source: source,
        output: outputInput.value.trim(),
        format: state.currentFormat,
        relative: chkRelative.checked,
        overwrite: chkOverwrite.checked,
        max_compression: chkMaxCompress.checked,
        exclude_junk: chkExcludeJunk.checked,
        optimize_media: chkOptimizeMedia ? chkOptimizeMedia.checked : false,
        target_size_mb: chkTargetLimit.checked ? parseFloat(targetSizeInput.value) || 25 : null,
        split_if_exceeds: chkSplitExceeds.checked,
      };

      const res = await fetch('/api/compress', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (data.success) {
        state.lastResult = data;
        renderResult(data);
        fetchHistory();
        showToast('Archive created successfully!');
      } else {
        errorMessage.textContent = data.error || 'Failed to compress archive.';
        localErrorAlert.style.display = 'flex';
      }
    } catch (err) {
      errorMessage.textContent = `Server communication error: ${err.message}`;
      localErrorAlert.style.display = 'flex';
    } finally {
      setCompressingState(false);
    }
  });

  function setCompressingState(isCompressing) {
    const btnText = btnCompressLocal.querySelector('.btn-text');
    const spinner = btnCompressLocal.querySelector('.btn-spinner');

    if (isCompressing) {
      btnCompressLocal.disabled = true;
      btnText.textContent = 'Compressing...';
      spinner.style.display = 'inline-block';
      localStatusText.textContent = 'Compressing archive, please wait...';
    } else {
      btnCompressLocal.disabled = false;
      btnText.textContent = 'Compress Archive';
      spinner.style.display = 'none';
      localStatusText.textContent = 'Ready to compress';
    }
  }

  function renderResult(data) {
    resultTitleText.textContent = `${data.filename} Created`;
    resultTimeText.textContent = `Completed in ${data.duration_seconds}s`;
    resultSavingsPill.textContent = `Saved ${data.saved_percentage}%`;

    statOrigSize.textContent = data.original_size_formatted;
    statCompSize.textContent = data.compressed_size_formatted;
    statSavedBytes.textContent = data.saved_bytes_formatted;
    statFormat.textContent = data.format.toUpperCase();

    resultOutputPath.textContent = data.output;

    // Handle Target Size Limit Banner & Multi-Part Display
    if (data.target_size_mb) {
      limitBanner.style.display = 'flex';

      if (data.is_split && data.parts && data.parts.length > 1) {
        limitBanner.className = 'limit-status-banner limit-success';
        limitBannerIcon.textContent = '✓';
        limitBannerTitle.textContent = `Split into ${data.parts.length} parts — All under ${data.target_size_mb} MB!`;
        limitBannerDesc.textContent = 'Each volume is ready for email attachment (Gmail/Outlook) or upload.';
        btnManualSplit.style.display = 'none';

        // Render Parts
        renderSplitParts(data.parts, data.join_command, data.standalone_parts);
      } else if (data.is_under_target) {
        limitBanner.className = 'limit-status-banner limit-success';
        limitBannerIcon.textContent = '✓';
        limitBannerTitle.textContent = `Under ${data.target_size_mb} MB Limit (${data.compressed_size_formatted})`;
        limitBannerDesc.textContent = 'Successfully reduced! Ready for email attachment or Discord upload.';
        btnManualSplit.style.display = 'none';
        splitPartsBox.style.display = 'none';
      } else {
        limitBanner.className = 'limit-status-banner limit-warning';
        limitBannerIcon.textContent = '!';
        limitBannerTitle.textContent = `Exceeds ${data.target_size_mb} MB Limit (${data.compressed_size_formatted})`;
        limitBannerDesc.textContent = 'Too large for single email attachment. Split into volumes or switch to .tar.xz format.';
        btnManualSplit.style.display = 'inline-flex';
        splitPartsBox.style.display = 'none';
      }
    } else {
      limitBanner.style.display = 'none';
      splitPartsBox.style.display = 'none';
    }

    localResultCard.style.display = 'block';
  }

  function renderSplitParts(parts, joinCmd, isStandalone) {
    splitPartsBox.style.display = 'block';
    splitCountLabel.textContent = parts.length;
    splitPartsList.innerHTML = '';

    parts.forEach(part => {
      const li = document.createElement('li');
      li.className = 'split-part-item';
      li.innerHTML = `
        <span class="split-part-name">${escapeHtml(part.filename)}</span>
        <span class="split-part-size">${part.size_formatted}</span>
        <a href="/api/download?path=${encodeURIComponent(part.path)}" class="btn btn-secondary btn-sm" title="Download part">
          Download
        </a>
      `;
      splitPartsList.appendChild(li);
    });

    const joinRow = document.querySelector('.join-command-row');
    if (joinRow) {
      if (isStandalone || !joinCmd) {
        joinRow.innerHTML = `
          <div style="font-size: 12px; color: var(--success-text); font-weight: 500; padding: 4px 0;">
            ✓ Each file above is a complete, standalone archive. Double-click any part to open and extract directly without joining!
          </div>
        `;
      } else {
        joinRow.innerHTML = `
          <span class="join-label">Reassembly Command:</span>
          <div class="join-code-container">
            <code id="join-command-code">${escapeHtml(joinCmd)}</code>
            <button type="button" class="btn-chip" id="btn-copy-join">Copy Command</button>
          </div>
        `;
        document.getElementById('btn-copy-join').addEventListener('click', () => {
          navigator.clipboard.writeText(joinCmd).then(() => {
            showToast('Reassembly command copied to clipboard');
          }).catch(() => {
            showToast('Command copied');
          });
        });
      }
    }
  }

  btnManualSplit.addEventListener('click', async () => {
    if (!state.lastResult || !state.lastResult.output) return;
    const targetMb = parseFloat(targetSizeInput.value) || 25;
    btnManualSplit.disabled = true;
    btnManualSplit.textContent = 'Splitting...';

    try {
      const res = await fetch('/api/split-file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: state.lastResult.output,
          chunk_mb: Math.max(1, targetMb - 0.5),
        }),
      });
      const data = await res.json();
      if (data.success && data.parts) {
        state.lastResult.is_split = true;
        state.lastResult.parts = data.parts;
        state.lastResult.join_command = data.join_command;
        renderResult(state.lastResult);
        showToast(`Split into ${data.parts.length} parts under ${targetMb} MB!`);
      } else {
        showToast(data.error || 'Failed to split archive');
      }
    } catch (err) {
      showToast(`Split error: ${err.message}`);
    } finally {
      btnManualSplit.disabled = false;
      btnManualSplit.textContent = 'Split into <25 MB Parts';
    }
  });

  // 8. Result Card Actions
  btnRevealFinder.addEventListener('click', async () => {
    if (!state.lastResult || !state.lastResult.output) return;
    try {
      const res = await fetch('/api/open-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: state.lastResult.output }),
      });
      const data = await res.json();
      if (data.success) {
        showToast('Opened in macOS Finder');
      } else {
        showToast(data.error || 'Could not open in Finder');
      }
    } catch (err) {
      showToast('Error communicating with Finder');
    }
  });

  btnDownloadResult.addEventListener('click', () => {
    if (!state.lastResult || !state.lastResult.output) return;
    const downloadUrl = `/api/download?path=${encodeURIComponent(state.lastResult.output)}`;
    window.location.href = downloadUrl;
  });

  // 9. Browser Upload Tab
  uploadPills.forEach(pill => {
    pill.addEventListener('click', () => {
      uploadPills.forEach(p => p.classList.remove('selected'));
      pill.classList.add('selected');
      const radio = pill.querySelector('input[type="radio"]');
      radio.checked = true;
      state.uploadFormat = radio.value;
    });
  });

  // Dropzone drag events
  ['dragenter', 'dragover'].forEach(eventName => {
    uploadDropzone.addEventListener(eventName, e => {
      e.preventDefault();
      e.stopPropagation();
      uploadDropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    uploadDropzone.addEventListener(eventName, e => {
      e.preventDefault();
      e.stopPropagation();
      uploadDropzone.classList.remove('dragover');
    });
  });

  uploadDropzone.addEventListener('drop', e => {
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      addStagedFiles(files);
    }
  });

  uploadFileInput.addEventListener('change', () => {
    if (uploadFileInput.files.length > 0) {
      addStagedFiles(Array.from(uploadFileInput.files));
    }
  });

  uploadFolderInput.addEventListener('change', () => {
    if (uploadFolderInput.files.length > 0) {
      addStagedFiles(Array.from(uploadFolderInput.files));
    }
  });

  function addStagedFiles(files) {
    state.stagedFiles = files;
    renderStagedFiles();
  }

  btnClearStaged.addEventListener('click', () => {
    state.stagedFiles = [];
    uploadFileInput.value = '';
    uploadFolderInput.value = '';
    renderStagedFiles();
  });

  function renderStagedFiles() {
    if (state.stagedFiles.length === 0) {
      stagedBox.style.display = 'none';
      btnCompressUpload.disabled = true;
      uploadStatusText.textContent = 'Select files to begin';
      return;
    }

    stagedBox.style.display = 'block';
    btnCompressUpload.disabled = false;

    let totalBytes = 0;
    stagedList.innerHTML = '';

    state.stagedFiles.slice(0, 10).forEach(file => {
      totalBytes += file.size;
      const li = document.createElement('li');
      li.className = 'staged-item';
      li.innerHTML = `
        <span class="staged-item-name">${escapeHtml(file.name)}</span>
        <span class="staged-item-size">${formatBytes(file.size)}</span>
      `;
      stagedList.appendChild(li);
    });

    if (state.stagedFiles.length > 10) {
      const extra = state.stagedFiles.length - 10;
      const li = document.createElement('li');
      li.className = 'staged-item';
      li.innerHTML = `<span class="staged-item-name" style="color: var(--text-muted);">...and ${extra} more files</span>`;
      stagedList.appendChild(li);
    }

    stagedCountLabel.textContent = `${state.stagedFiles.length} file(s) selected (${formatBytes(totalBytes)})`;
    uploadStatusText.textContent = `Ready to compress ${state.stagedFiles.length} files`;
  }

  // Upload & Compress Submission
  btnCompressUpload.addEventListener('click', async () => {
    if (state.stagedFiles.length === 0) return;

    const btnText = btnCompressUpload.querySelector('.btn-text');
    const spinner = btnCompressUpload.querySelector('.btn-spinner');

    btnCompressUpload.disabled = true;
    btnText.textContent = 'Compressing...';
    spinner.style.display = 'inline-block';
    uploadStatusText.textContent = 'Uploading & compressing files...';

    const formData = new FormData();
    formData.append('format', state.uploadFormat);
    state.stagedFiles.forEach(f => {
      formData.append('files', f);
    });

    try {
      const res = await fetch('/api/upload-compress', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || `Upload failed (Status ${res.status})`);
      }

      // Stream download to browser
      const blob = await res.blob();
      const contentDisposition = res.headers.get('Content-Disposition') || '';
      let filename = `archive.${state.uploadFormat}`;
      const match = contentDisposition.match(/filename="?([^"]+)"?/);
      if (match && match[1]) {
        filename = match[1];
      }

      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(downloadUrl);

      showToast(`Downloaded: ${filename}`);
      uploadStatusText.textContent = `Successfully downloaded ${filename}`;
      fetchHistory();
    } catch (err) {
      showToast(err.message);
      uploadStatusText.textContent = `Error: ${err.message}`;
    } finally {
      btnCompressUpload.disabled = false;
      btnText.textContent = 'Compress & Download';
      spinner.style.display = 'none';
    }
  });

  // 10. Session History
  async function fetchHistory() {
    try {
      const res = await fetch('/api/history');
      if (res.ok) {
        const data = await res.json();
        state.history = data.history || [];
        renderHistory();
      }
    } catch (err) {
      console.warn('History fetch error:', err);
    }
  }

  btnRefreshHistory.addEventListener('click', () => {
    fetchHistory();
    showToast('History refreshed');
  });

  function renderHistory() {
    historyCounter.textContent = state.history.length;

    if (state.history.length === 0) {
      historyEmpty.style.display = 'flex';
      historyList.style.display = 'none';
      return;
    }

    historyEmpty.style.display = 'none';
    historyList.style.display = 'flex';
    historyList.innerHTML = '';

    state.history.forEach(item => {
      const el = document.createElement('div');
      el.className = 'history-item';
      el.innerHTML = `
        <div class="history-meta">
          <span class="history-filename">${escapeHtml(item.filename)}</span>
          <span class="history-stats">
            <span>${item.compressed_size_formatted}</span>
            <span>•</span>
            <span>Saved ${item.saved_percentage}%</span>
            <span>•</span>
            <span>${item.timestamp || 'Just now'}</span>
          </span>
        </div>
        <div class="history-actions">
          <button type="button" class="btn btn-secondary btn-sm btn-hist-finder" data-path="${escapeHtml(item.output)}" title="Reveal in Finder">
            Finder
          </button>
          <a href="/api/download?path=${encodeURIComponent(item.output)}" class="btn btn-secondary btn-sm" title="Download">
            Download
          </a>
        </div>
      `;

      el.querySelector('.btn-hist-finder').addEventListener('click', async (e) => {
        const path = e.target.getAttribute('data-path');
        if (!path) return;
        try {
          await fetch('/api/open-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
          });
          showToast('Revealed in Finder');
        } catch (err) {
          showToast('Failed to reveal');
        }
      });

      historyList.appendChild(el);
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ==========================================================================
  // Video Downloader Logic (YouTube & Pinterest)
  // ==========================================================================
  const videoUrlInput = document.getElementById('video-url-input');
  const btnPasteVideoUrl = document.getElementById('btn-paste-video-url');
  const btnInspectVideo = document.getElementById('btn-inspect-video');
  const videoPlatformBadge = document.getElementById('video-platform-badge');
  const videoPlatformName = document.getElementById('video-platform-name');
  const videoErrorAlert = document.getElementById('video-error-alert');
  const videoErrorMessage = document.getElementById('video-error-message');
  const videoPreviewCard = document.getElementById('video-preview-card');
  const videoThumbImg = document.getElementById('video-thumb-img');
  const videoDurationBadge = document.getElementById('video-duration-badge');
  const previewPlatformTag = document.getElementById('preview-platform-tag');
  const previewAspectTag = document.getElementById('preview-aspect-tag');
  const videoTitleDisplay = document.getElementById('video-title-display');
  const videoUploaderDisplay = document.getElementById('video-uploader-display');
  const videoDimensionsDisplay = document.getElementById('video-dimensions-display');
  const videoOptionsSection = document.getElementById('video-options-section');
  const vformatCards = document.querySelectorAll('.vformat-card');
  const videoResolutionRow = document.getElementById('video-resolution-row');
  const videoResolutionChips = document.getElementById('video-resolution-chips');
  const videoDestInput = document.getElementById('video-dest-input');
  const btnBrowseVideoDest = document.getElementById('btn-browse-video-dest');
  const chipVideoDownloads = document.getElementById('chip-video-downloads');
  const chipVideoDesktop = document.getElementById('chip-video-desktop');
  const chipVideoMovies = document.getElementById('chip-video-movies');
  const videoCustomName = document.getElementById('video-custom-name');
  const btnDownloadVideoMac = document.getElementById('btn-download-video-mac');
  const btnDownloadVideoBrowser = document.getElementById('btn-download-video-browser');
  const videoStatusText = document.getElementById('video-status-text');
  const videoDownloadBtnText = document.getElementById('video-download-btn-text');
  const videoResultCard = document.getElementById('video-result-card');
  const vresultTitleText = document.getElementById('vresult-title-text');
  const vstatSize = document.getElementById('vstat-size');
  const vstatDimensions = document.getElementById('vstat-dimensions');
  const vstatFormat = document.getElementById('vstat-format');
  const vstatPlatform = document.getElementById('vstat-platform');
  const vresultOutputPath = document.getElementById('vresult-output-path');
  const btnRevealVideoFinder = document.getElementById('btn-reveal-video-finder');
  const btnCompressDownloadedVideo = document.getElementById('btn-compress-downloaded-video');

  state.videoMedia = null;
  state.videoFormat = 'mp4';
  state.videoResolution = 'original';
  state.lastDownloadedVideo = null;

  function setupVideoDownloader() {
    if (!videoUrlInput) return;

    // Live URL Detection
    videoUrlInput.addEventListener('input', () => {
      detectAndShowPlatform(videoUrlInput.value);
    });

    // Paste button
    if (btnPasteVideoUrl) {
      btnPasteVideoUrl.addEventListener('click', async () => {
        try {
          const text = await navigator.clipboard.readText();
          if (text) {
            videoUrlInput.value = text.trim();
            detectAndShowPlatform(videoUrlInput.value);
            showToast('Pasted URL from clipboard');
          }
        } catch (e) {
          videoUrlInput.focus();
          showToast('Please paste using Cmd+V');
        }
      });
    }

    // Inspect Media button
    if (btnInspectVideo) {
      btnInspectVideo.addEventListener('click', () => inspectVideo());
    }
    videoUrlInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        inspectVideo();
      }
    });

    // Format Cards Selection
    vformatCards.forEach((card) => {
      card.addEventListener('click', () => {
        vformatCards.forEach((c) => c.classList.remove('selected'));
        card.classList.add('selected');
        const radio = card.querySelector('input[type="radio"]');
        if (radio) {
          radio.checked = true;
          state.videoFormat = radio.value;
          updateVideoActionLabels();
        }
      });
    });

    // Destination Shortcuts
    if (chipVideoDownloads) {
      chipVideoDownloads.addEventListener('click', () => {
        if (state.systemInfo?.downloads_dir) videoDestInput.value = state.systemInfo.downloads_dir;
      });
    }
    if (chipVideoDesktop) {
      chipVideoDesktop.addEventListener('click', () => {
        if (state.systemInfo?.desktop_dir) videoDestInput.value = state.systemInfo.desktop_dir;
      });
    }
    if (chipVideoMovies) {
      chipVideoMovies.addEventListener('click', () => {
        if (state.systemInfo?.home_dir) videoDestInput.value = `${state.systemInfo.home_dir}/Movies`;
      });
    }

    // Browse Destination Folder
    if (btnBrowseVideoDest) {
      btnBrowseVideoDest.addEventListener('click', async () => {
        try {
          const res = await fetch('/api/browse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'folder', prompt: 'Select destination folder for video downloads' })
          });
          const data = await res.json();
          if (data.success && data.path) {
            videoDestInput.value = data.path;
          }
        } catch (err) {
          showToast('Could not open folder picker');
        }
      });
    }

    // Download to Mac Action
    if (btnDownloadVideoMac) {
      btnDownloadVideoMac.addEventListener('click', () => startDownloadToMac());
    }

    // Download via Browser Action
    if (btnDownloadVideoBrowser) {
      btnDownloadVideoBrowser.addEventListener('click', () => startDownloadBrowser());
    }

    // Reveal in Finder Action
    if (btnRevealVideoFinder) {
      btnRevealVideoFinder.addEventListener('click', async () => {
        if (!state.lastDownloadedVideo?.output_path) return;
        try {
          await fetch('/api/open-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: state.lastDownloadedVideo.output_path })
          });
          showToast('Revealed in Finder');
        } catch (err) {
          showToast('Failed to reveal');
        }
      });
    }

    // Send to Compressor Action
    if (btnCompressDownloadedVideo) {
      btnCompressDownloadedVideo.addEventListener('click', () => {
        if (!state.lastDownloadedVideo?.output_path) return;
        const targetPath = state.lastDownloadedVideo.output_path;
        const tabLocalBtn = document.getElementById('tab-local-btn');
        if (tabLocalBtn) {
          tabLocalBtn.click();
          setSourcePath(targetPath);
          showToast('Loaded video into File Compressor!');
        }
      });
    }
  }

  function detectAndShowPlatform(url) {
    const trimmed = (url || '').trim().toLowerCase();
    if (!videoPlatformBadge) return;

    if (trimmed.includes('instagram.com') || trimmed.includes('instagr.am') || trimmed.includes('ig.me')) {
      videoPlatformBadge.className = 'platform-chip instagram';
      videoPlatformName.textContent = 'Instagram Reel';
      videoPlatformBadge.style.display = 'inline-flex';
    } else if (trimmed.includes('youtube.com') || trimmed.includes('youtu.be')) {
      videoPlatformBadge.className = 'platform-chip youtube';
      videoPlatformName.textContent = 'YouTube';
      videoPlatformBadge.style.display = 'inline-flex';
    } else if (trimmed.includes('pinterest.com') || trimmed.includes('pin.it')) {
      videoPlatformBadge.className = 'platform-chip pinterest';
      videoPlatformName.textContent = 'Pinterest';
      videoPlatformBadge.style.display = 'inline-flex';
    } else if (trimmed.startsWith('http')) {
      videoPlatformBadge.className = 'platform-chip generic';
      videoPlatformName.textContent = 'Web Video';
      videoPlatformBadge.style.display = 'inline-flex';
    } else {
      videoPlatformBadge.style.display = 'none';
    }
  }

  async function inspectVideo() {
    const url = (videoUrlInput.value || '').trim();
    if (!url) {
      showVideoError('Please enter an Instagram Reel, YouTube, or Pinterest link.');
      return;
    }

    hideVideoError();
    videoResultCard.style.display = 'none';
    const btnText = btnInspectVideo.querySelector('.btn-text');
    const spinner = btnInspectVideo.querySelector('.btn-spinner');
    btnInspectVideo.disabled = true;
    if (btnText) btnText.textContent = 'Inspecting...';
    if (spinner) spinner.style.display = 'inline-block';

    try {
      const res = await fetch('/api/video/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await res.json();

      if (!res.ok || !data.success) {
        showVideoError(data.error || 'Failed to inspect media. Please check the URL.');
        return;
      }

      state.videoMedia = data;
      renderVideoMediaPreview(data);
      showToast('Media inspected successfully!');
    } catch (err) {
      showVideoError(`Network error while inspecting media: ${err.message}`);
    } finally {
      btnInspectVideo.disabled = false;
      if (btnText) btnText.textContent = 'Inspect Video';
      if (spinner) spinner.style.display = 'none';
    }
  }

  function renderVideoMediaPreview(media) {
    if (!media) return;

    // Fill preview card
    if (media.thumbnail) {
      videoThumbImg.src = media.thumbnail;
      videoThumbImg.style.display = 'block';
    } else {
      videoThumbImg.style.display = 'none';
    }

    videoDurationBadge.textContent = media.duration_formatted || 'Video';
    previewPlatformTag.textContent = media.platform || 'Video';
    previewAspectTag.textContent = media.aspect_label || 'Native Aspect';
    videoTitleDisplay.textContent = media.title || 'Untitled Video';
    videoUploaderDisplay.textContent = media.uploader || 'Creator';

    // Dimension Guarantee highlight
    videoDimensionsDisplay.textContent = media.dimensions || 'Original Dimensions';

    // Default destination folder
    if (!videoDestInput.value && state.systemInfo) {
      videoDestInput.value = state.systemInfo.downloads_dir || state.systemInfo.desktop_dir || '';
    }

    // Build Resolution Chips
    renderResolutionChips(media.available_resolutions || []);

    videoPreviewCard.style.display = 'flex';
    videoOptionsSection.style.display = 'block';
    updateVideoActionLabels();
  }

  function renderResolutionChips(resolutions) {
    videoResolutionChips.innerHTML = '';

    // "Original Native" chip is always first & default
    const origChip = document.createElement('button');
    origChip.type = 'button';
    origChip.className = 'btn-chip active-chip';
    origChip.setAttribute('data-res', 'original');
    origChip.innerHTML = 'Original Native (Same Pixels)';
    origChip.addEventListener('click', () => selectResolution('original', origChip));
    videoResolutionChips.appendChild(origChip);

    state.videoResolution = 'original';

    // Add specific resolutions if available
    resolutions.forEach((r) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'btn-chip';
      chip.setAttribute('data-res', String(r));
      chip.textContent = `${r}p`;
      chip.addEventListener('click', () => selectResolution(r, chip));
      videoResolutionChips.appendChild(chip);
    });
  }

  function selectResolution(resVal, activeBtn) {
    state.videoResolution = resVal;
    videoResolutionChips.querySelectorAll('.btn-chip').forEach((b) => b.classList.remove('active-chip'));
    if (activeBtn) activeBtn.classList.add('active-chip');
    updateVideoActionLabels();
  }

  function updateVideoActionLabels() {
    const isAudio = ['mp3', 'm4a', 'wav'].includes(state.videoFormat);
    if (isAudio) {
      videoResolutionRow.style.display = 'none';
      if (videoDownloadBtnText) videoDownloadBtnText.textContent = `Extract & Download .${state.videoFormat} Audio`;
      if (videoStatusText) videoStatusText.textContent = `Ready to extract high quality .${state.videoFormat} audio`;
    } else {
      videoResolutionRow.style.display = 'flex';
      const dimNote = (state.videoMedia?.dimensions || 'same dimensions');
      if (videoDownloadBtnText) videoDownloadBtnText.textContent = `Download .${state.videoFormat} (Same Pixels)`;
      if (videoStatusText) videoStatusText.textContent = `Preserves ${dimNote}`;
    }
  }

  async function startDownloadToMac() {
    const url = (videoUrlInput.value || '').trim();
    if (!url) {
      showVideoError('Please enter a video URL.');
      return;
    }

    const output_dir = (videoDestInput.value || '').trim();
    const custom_name = (videoCustomName.value || '').trim();
    const target_ext = state.videoFormat || 'mp4';
    const resolution = state.videoResolution === 'original' ? null : parseInt(state.videoResolution, 10);

    hideVideoError();
    videoResultCard.style.display = 'none';

    const btnText = btnDownloadVideoMac.querySelector('.btn-text');
    const spinner = btnDownloadVideoMac.querySelector('.btn-spinner');
    btnDownloadVideoMac.disabled = true;
    if (btnDownloadVideoBrowser) btnDownloadVideoBrowser.disabled = true;
    if (btnText) btnText.textContent = 'Downloading...';
    if (spinner) spinner.style.display = 'inline-block';
    videoStatusText.textContent = 'Downloading media & verifying exact pixel dimensions...';

    try {
      const res = await fetch('/api/video/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          output_dir,
          target_ext,
          resolution,
          custom_name
        })
      });
      const data = await res.json();

      if (!res.ok || !data.success) {
        showVideoError(data.error || 'Download failed. Please try again.');
        videoStatusText.textContent = 'Download failed';
        return;
      }

      state.lastDownloadedVideo = data;
      renderDownloadSuccess(data);
      showToast('Video downloaded successfully!');
      videoStatusText.textContent = 'Saved to your Mac';
    } catch (err) {
      showVideoError(`Download error: ${err.message}`);
      videoStatusText.textContent = 'Error occurred';
    } finally {
      btnDownloadVideoMac.disabled = false;
      if (btnDownloadVideoBrowser) btnDownloadVideoBrowser.disabled = false;
      updateVideoActionLabels();
      if (spinner) spinner.style.display = 'none';
    }
  }

  function startDownloadBrowser() {
    const url = (videoUrlInput.value || '').trim();
    if (!url) {
      showVideoError('Please enter a video URL.');
      return;
    }
    const target_ext = state.videoFormat || 'mp4';
    const resVal = state.videoResolution === 'original' ? '' : `&resolution=${state.videoResolution}`;
    const dlUrl = `/api/video/download-browser?url=${encodeURIComponent(url)}&target_ext=${encodeURIComponent(target_ext)}${resVal}`;

    showToast('Starting browser download...');
    window.location.href = dlUrl;
  }

  function renderDownloadSuccess(data) {
    vresultTitleText.textContent = data.filename || 'Downloaded File';
    vstatSize.textContent = data.size_formatted || '-';
    vstatDimensions.textContent = data.dimensions || 'Original Pixels Preserved';
    vstatFormat.textContent = `.${(data.target_ext || 'mp4').toUpperCase()}`;
    vstatPlatform.textContent = data.platform || 'Web';
    vresultOutputPath.textContent = data.output_path || data.output_dir || '-';

    videoResultCard.style.display = 'block';
    videoResultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function showVideoError(msg) {
    if (videoErrorMessage) videoErrorMessage.textContent = msg;
    if (videoErrorAlert) videoErrorAlert.style.display = 'flex';
  }

  function hideVideoError() {
    if (videoErrorAlert) videoErrorAlert.style.display = 'none';
  }

  // Start initialization
  init();
  setupVideoDownloader();
});
