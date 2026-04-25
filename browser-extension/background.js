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

// ── Inline extraction function (injected via executeScript) ─

function extractPageContent() {
  const title = document.title || '';
  const url = window.location.href;
  const hostname = window.location.hostname;

  // Try common article containers
  const selectors = [
    'article', 'main', '[role="main"]',
    '.post-content', '.entry-content', '.article-content',
    '.content', '#content',
    '.rich_media_content',        // WeChat
    '.Post-RichTextContainer',    // Zhihu
    '.article-holder',            // Jianshu
  ];

  let articleEl = null;
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el && el.innerText.trim().length > 300) {
      articleEl = el;
      break;
    }
  }

  // Fallback: find largest text block
  if (!articleEl) {
    let bestEl = null, bestScore = 0;
    for (const p of document.querySelectorAll('p')) {
      const parent = p.parentElement;
      if (!parent) continue;
      const text = parent.innerText || '';
      const tag = parent.tagName.toLowerCase();
      const cls = (parent.className || '').toLowerCase();
      const id = (parent.id || '').toLowerCase();
      if (/nav|menu|footer|sidebar|comment|ad|header/.test(tag + cls + id)) continue;
      if (text.length > bestScore) {
        bestScore = text.length;
        bestEl = parent;
      }
    }
    articleEl = bestEl;
  }

  // Fallback: body
  if (!articleEl) articleEl = document.body;

  // Clean and convert
  const clone = articleEl.cloneNode(true);
  clone.querySelectorAll('script, style, nav, header, footer, aside, .advertisement, .ad, .comments, .sidebar, iframe, form, button, input')
    .forEach(el => el.remove());

  let content = '';
  function walk(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      content += node.textContent;
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const tag = node.tagName.toLowerCase();
      if (tag === 'p' || /^h[1-6]$/.test(tag) || tag === 'blockquote' || tag === 'pre' || tag === 'li') {
        content += '\n\n';
      } else if (tag === 'br') {
        content += '\n';
      }
      for (const child of node.childNodes) walk(child);
      if (tag === 'p' || /^h[1-6]$/.test(tag) || tag === 'blockquote' || tag === 'pre' || tag === 'li') {
        content += '\n\n';
      }
    }
  }
  walk(clone);

  content = content.replace(/\n{3,}/g, '\n\n').trim();

  return {
    title: title.trim(),
    url: url,
    hostname: hostname,
    content: content,
    excerpt: content.slice(0, 200).replace(/\n/g, ' '),
    wordCount: content.length,
  };
}

// ── Send Full Page ──────────────────────────────────────────

async function sendPageToSageMate(tab) {
  try {
    // 1. Extract content directly via executeScript (no message passing)
    const [{ result: extracted }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPageContent,
    });

    if (!extracted) {
      throw new Error('提取失败（页面可能无法访问）');
    }

    const data = extracted;

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
