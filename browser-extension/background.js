/**
 * SageMate Clipper — Background Service Worker
 * Handles: context menus, keyboard shortcuts, notifications, API calls
 */

const SAGEMATE_HOST = 'http://localhost:8000';
const API_CLIP = `${SAGEMATE_HOST}/api/v1/clip`;
const API_QUERY = `${SAGEMATE_HOST}/api/v1/query`;

// ── Context Menus ───────────────────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
  // 1. Right-click on page → send full page
  chrome.contextMenus.create({
    id: 'send-page',
    title: '🌿 发送到 SageMate',
    contexts: ['page'],
    documentUrlPatterns: ['http://*/*', 'https://*/*'],
  });

  // 2. Right-click on selection → ask SageMate
  chrome.contextMenus.create({
    id: 'ask-selection',
    title: '🌿 Ask SageMate',
    contexts: ['selection'],
    documentUrlPatterns: ['http://*/*', 'https://*/*'],
  });

  console.log('[SageMate Clipper] Context menus created');
});

// ── Keyboard Shortcut ───────────────────────────────────────

chrome.commands.onCommand.addListener((command) => {
  if (command === 'send-to-sagemate') {
    chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
      if (tab?.id) {
        sendPageToSageMate(tab);
      }
    });
  }
});

// ── Context Menu Click Handler ──────────────────────────────

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!tab?.id) return;

  switch (info.menuItemId) {
    case 'send-page':
      sendPageToSageMate(tab);
      break;

    case 'ask-selection':
      if (info.selectionText) {
        askSageMate(tab, info.selectionText);
      }
      break;
  }
});

// ── Send Full Page ──────────────────────────────────────────

async function sendPageToSageMate(tab) {
  try {
    // 1. Ensure content script is injected, then extract
    let response;
    try {
      response = await chrome.tabs.sendMessage(tab.id, { action: 'extract' });
    } catch (e) {
      // Content script not loaded — inject it first
      if (e.message?.includes('Could not establish connection')) {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content.js'],
        });
        // Wait a tiny bit for the script to register its listener
        await new Promise(r => setTimeout(r, 100));
        response = await chrome.tabs.sendMessage(tab.id, { action: 'extract' });
      } else {
        throw e;
      }
    }

    if (!response || !response.success) {
      throw new Error(response?.error || '提取失败');
    }

    const data = response.data;

    // 2. Send to SageMate backend
    const result = await fetch(API_CLIP, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: data.title,
        url: data.url,
        content: data.content,
        hostname: data.hostname,
        auto_compile: true,
        source_type: 'browser_clipper',
      }),
    });

    const json = await result.json();

    if (!result.ok) {
      throw new Error(json.detail || json.message || `HTTP ${result.status}`);
    }

    // 3. Notify user
    notify(
      '✅ 已发送到 SageMate',
      `《${data.title}》已保存${json.status === 'processing' ? '，正在编译中...' : ''}`
    );

  } catch (err) {
    console.error('[SageMate Clipper] Send failed:', err);
    let msg = err.message;
    if (msg.includes('Could not establish connection')) {
      msg = '页面未加载完成，请刷新后重试';
    } else if (msg.includes('Failed to fetch')) {
      msg = '无法连接到 SageMate（localhost:8000）';
    }
    notify('❌ 发送失败', msg);
  }
}

// ── Ask SageMate (selected text) ────────────────────────────

async function askSageMate(tab, selectedText) {
  try {
    // Truncate if too long
    const question = selectedText.length > 500
      ? selectedText.slice(0, 500) + '...'
      : selectedText;

    // Call query API
    const result = await fetch(API_QUERY, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: `关于以下内容，我的知识库怎么说？\n\n"${question}"`,
      }),
    });

    const json = await result.json();

    if (!result.ok) {
      throw new Error(json.detail || json.message || `HTTP ${result.status}`);
    }

    // Extract answer text
    const answer = json.answer || json.response || '无回答';
    const truncated = answer.length > 150 ? answer.slice(0, 150) + '...' : answer;

    notify('🌿 SageMate 回答', truncated);

  } catch (err) {
    console.error('[SageMate Clipper] Ask failed:', err);
    let msg = err.message;
    if (msg.includes('Failed to fetch')) {
      msg = '无法连接到 SageMate';
    }
    notify('❌ 问答失败', msg);
  }
}

// ── Notification Helper ─────────────────────────────────────

function notify(title, message) {
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icons/icon128.png',
    title,
    message,
    priority: 1,
  });
}
