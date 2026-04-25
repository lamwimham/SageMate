/**
 * SageMate Clipper — Content Script
 * Injected into every page to extract article content.
 */

(function () {
  'use strict';

  // Simple readability-like extraction
  function extractArticle() {
    const title = document.title || '';
    const url = window.location.href;
    const hostname = window.location.hostname;

    // Try common article containers
    const selectors = [
      'article',
      'main',
      '[role="main"]',
      '.post-content',
      '.entry-content',
      '.article-content',
      '.content',
      '#content',
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

    // Fallback: find the largest text block
    if (!articleEl) {
      articleEl = findLargestTextBlock();
    }

    // Fallback: body
    if (!articleEl) {
      articleEl = document.body;
    }

    const content = cleanAndConvert(articleEl);
    const excerpt = content.slice(0, 200).replace(/\n/g, ' ');

    return {
      title: title.trim(),
      url: url,
      hostname: hostname,
      content: content,
      excerpt: excerpt,
      wordCount: content.length,
    };
  }

  function findLargestTextBlock() {
    const paragraphs = document.querySelectorAll('p');
    let bestEl = null;
    let bestScore = 0;

    for (const p of paragraphs) {
      const parent = p.parentElement;
      if (!parent) continue;

      const text = parent.innerText || '';
      const score = text.length;

      // Penalize navigation, footer, sidebar
      const tag = parent.tagName.toLowerCase();
      const cls = (parent.className || '').toLowerCase();
      const id = (parent.id || '').toLowerCase();

      if (/nav|menu|footer|sidebar|comment|ad|header/.test(tag + cls + id)) {
        continue;
      }

      if (score > bestScore) {
        bestScore = score;
        bestEl = parent;
      }
    }

    return bestEl;
  }

  function cleanAndConvert(element) {
    // Clone to avoid modifying the real DOM
    const clone = element.cloneNode(true);

    // Remove unwanted elements
    const unwanted = clone.querySelectorAll('script, style, nav, header, footer, aside, .advertisement, .ad, .comments, .sidebar, iframe, form, button, input');
    unwanted.forEach(el => el.remove());

    // Convert to markdown-like text
    let text = elementToMarkdown(clone);

    // Clean up
    text = text
      .replace(/\n{3,}/g, '\n\n')
      .replace(/^\s+|\s+$/g, '');

    return text;
  }

  function elementToMarkdown(el) {
    let result = '';

    for (const node of el.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        result += node.textContent;
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        const tag = node.tagName.toLowerCase();

        switch (tag) {
          case 'h1':
          case 'h2':
          case 'h3':
          case 'h4':
          case 'h5':
          case 'h6':
            const level = parseInt(tag[1]);
            result += '\n\n' + '#'.repeat(level) + ' ' + elementToMarkdown(node) + '\n\n';
            break;
          case 'p':
            result += '\n\n' + elementToMarkdown(node) + '\n\n';
            break;
          case 'br':
            result += '\n';
            break;
          case 'li':
            result += '\n- ' + elementToMarkdown(node);
            break;
          case 'img':
            const src = node.getAttribute('src') || '';
            const alt = node.getAttribute('alt') || '';
            if (src) {
              result += `\n\n![${alt}](${src})\n\n`;
            }
            break;
          case 'a':
            const href = node.getAttribute('href') || '';
            const text = elementToMarkdown(node);
            if (href && !href.startsWith('javascript:')) {
              result += `[${text}](${href})`;
            } else {
              result += text;
            }
            break;
          case 'blockquote':
            result += '\n\n> ' + elementToMarkdown(node).replace(/\n/g, '\n> ') + '\n\n';
            break;
          case 'pre':
          case 'code':
            result += '\n\n```\n' + node.innerText + '\n```\n\n';
            break;
          case 'div':
          case 'section':
          case 'article':
          case 'main':
          case 'span':
          case 'strong':
          case 'em':
          case 'b':
          case 'i':
            result += elementToMarkdown(node);
            break;
          default:
            result += elementToMarkdown(node);
        }
      }
    }

    return result;
  }

  // Listen for messages from popup
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'extract') {
      try {
        const data = extractArticle();
        sendResponse({ success: true, data });
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    }
    return true; // async response
  });
})();
