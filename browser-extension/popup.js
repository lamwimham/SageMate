/**
 * SageMate Clipper — Popup Script
 * Handles UI interactions and communication with content script + backend.
 */

(function () {
  'use strict';

  const SAGEMATE_HOST = 'http://localhost:8000';
  const API_CLIP = `${SAGEMATE_HOST}/api/v1/clip`;
  const API_HEALTH = `${SAGEMATE_HOST}/api/v1/health`;

  // DOM elements
  const els = {
    statusBadge: document.getElementById('status-badge'),
    connectionError: document.getElementById('connection-error'),
    contentArea: document.getElementById('content-area'),
    previewTitle: document.getElementById('preview-title'),
    previewUrl: document.getElementById('preview-url'),
    previewContent: document.getElementById('preview-content'),
    wordCount: document.getElementById('word-count'),
    autoCompile: document.getElementById('auto-compile'),
    btnSend: document.getElementById('btn-send'),
    resultArea: document.getElementById('result-area'),
    resultMessage: document.getElementById('result-message'),
    linkRaw: document.getElementById('link-raw'),
    linkWiki: document.getElementById('link-wiki'),
  };

  let extractedData = null;
  let isConnected = false;

  // ── Initialization ─────────────────────────────────────────

  async function init() {
    // Check sagemate connection
    await checkConnection();

    if (!isConnected) {
      showConnectionError();
      return;
    }

    // Extract content from current tab
    await extractContent();
  }

  // ── Connection Check ───────────────────────────────────────

  async function checkConnection() {
    try {
      const resp = await fetch(API_HEALTH, { method: 'GET', signal: AbortSignal.timeout(3000) });
      if (resp.ok) {
        isConnected = true;
        updateStatus('connected', '已连接');
      } else {
        throw new Error('Health check failed');
      }
    } catch (err) {
      isConnected = false;
      updateStatus('disconnected', '未连接');
    }
  }

  function updateStatus(type, text) {
    els.statusBadge.className = `status-badge ${type}`;
    els.statusBadge.textContent = text;
  }

  function showConnectionError() {
    els.connectionError.classList.remove('hidden');
    els.contentArea.classList.add('hidden');
    els.actions.classList.add('hidden');
  }

  // ── Content Extraction ─────────────────────────────────────

  async function extractContent() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.id) {
        throw new Error('No active tab');
      }

      // Send message to content script
      const response = await chrome.tabs.sendMessage(tab.id, { action: 'extract' });

      if (!response.success) {
        throw new Error(response.error || '提取失败');
      }

      extractedData = response.data;
      renderPreview(extractedData);
      els.btnSend.disabled = false;

    } catch (err) {
      console.error('Extract failed:', err);
      els.previewTitle.textContent = '无法提取内容';
      els.previewContent.textContent = err.message;
      els.btnSend.disabled = true;
    }
  }

  function renderPreview(data) {
    els.previewTitle.textContent = data.title || '无标题';
    els.previewUrl.textContent = data.url;
    els.previewContent.textContent = data.excerpt || data.content.slice(0, 300);
    els.wordCount.textContent = `约 ${data.wordCount.toLocaleString()} 字`;
  }

  // ── Send to SageMate ───────────────────────────────────────

  async function sendToSageMate() {
    if (!extractedData) return;

    setLoading(true);

    const payload = {
      title: extractedData.title,
      url: extractedData.url,
      content: extractedData.content,
      hostname: extractedData.hostname,
      auto_compile: els.autoCompile.checked,
      source_type: 'browser_clipper',
    };

    try {
      const resp = await fetch(API_CLIP, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const result = await resp.json();

      if (!resp.ok) {
        throw new Error(result.detail || result.message || `HTTP ${resp.status}`);
      }

      showResult('success', result.message || '发送成功！');
      setLinks(result.source_slug);

    } catch (err) {
      console.error('Send failed:', err);
      let msg = err.message;
      if (msg.includes('Failed to fetch') || msg.includes('NetworkError')) {
        msg = '无法连接到 SageMate，请检查服务是否运行';
      }
      showResult('error', msg);
    } finally {
      setLoading(false);
    }
  }

  function setLoading(loading) {
    els.btnSend.disabled = loading;
    if (loading) {
      els.btnSend.innerHTML = '<div class="spinner"></div><span>发送中...</span>';
    } else {
      els.btnSend.innerHTML = '<span class="btn-icon">🚀</span><span class="btn-text">发送到 SageMate</span>';
    }
  }

  function showResult(type, message) {
    els.resultArea.classList.remove('hidden');
    els.resultMessage.className = `result-message ${type}`;
    els.resultMessage.textContent = message;
  }

  function setLinks(slug) {
    els.linkRaw.href = `${SAGEMATE_HOST}/raw`;
    if (slug) {
      els.linkWiki.href = `${SAGEMATE_HOST}/wiki/${slug}`;
      els.linkWiki.classList.remove('hidden');
    } else {
      els.linkWiki.classList.add('hidden');
    }
  }

  // ── Event Listeners ────────────────────────────────────────

  els.btnSend.addEventListener('click', sendToSageMate);

  // ── Start ──────────────────────────────────────────────────

  init();
})();
