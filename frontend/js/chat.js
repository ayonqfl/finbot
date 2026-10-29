/* ═══════════════════════════════════════════════
   finbot — Chat UI Logic (jQuery)
   Handles: send message, receive response,
            format picker (PDF/CSV), download btn
═══════════════════════════════════════════════ */

/* ── State ── */
let pendingExport = null;   // { symbol, data_type } — stored after ask_format
let isBusy = false;

$(function () {

  /* ── Auto-resize textarea ── */
  $('#msgInput').on('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
  });

  /* ── Send on Enter (Shift+Enter = newline) ── */
  $('#msgInput').on('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  /* ── Health check on load ── */
  checkHealth();

});

/* ════════════════════════════════════════════
   HEALTH CHECK
════════════════════════════════════════════ */
function checkHealth() {
  $.get('/health')
    .done(function (data) {
      setStatusDot('#dbDot',     '#dbLabel',     data.db,     'DB');
      setStatusDot('#ollamaDot', '#ollamaLabel', data.ollama, 'LLM');
    })
    .fail(function () {
      setStatusDot('#dbDot',     '#dbLabel',     'error', 'DB');
      setStatusDot('#ollamaDot', '#ollamaLabel', 'error', 'LLM');
    });
}

function setStatusDot(dotSel, labelSel, status, name) {
  const ok = status === 'ok';
  $(dotSel).removeClass('online offline').addClass(ok ? 'online' : 'offline');
  $(labelSel).text(ok ? `${name}: OK` : `${name}: Error`);
}

/* ════════════════════════════════════════════
   SEND MESSAGE
════════════════════════════════════════════ */
function sendMessage() {
  if (isBusy) return;
  const text = $('#msgInput').val().trim();
  if (!text) return;

  appendUserMsg(text);
  $('#msgInput').val('').css('height', 'auto');
  setLoading(true);

  $.ajax({
    url: '/chat/',
    type: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({ message: text }),
    success: function (res) {
      handleAgentResponse(res);
    },
    error: function (xhr) {
      const err = xhr.responseJSON?.content || 'Something went wrong. Please try again.';
      appendBotMsg(err, 'error');
    },
    complete: function () {
      setLoading(false);
    }
  });
}

/* ════════════════════════════════════════════
   HANDLE AGENT RESPONSE
════════════════════════════════════════════ */
function handleAgentResponse(res) {
  switch (res.type) {

    case 'ask_format':
      /* Agent wants to know: PDF or CSV? */
      pendingExport = { symbol: res.symbol, data_type: res.data_type };
      appendFormatPicker(res.content, res.symbol, res.data_type);
      break;

    case 'text':
      appendBotMsg(res.content);
      break;

    case 'error':
      appendBotMsg(res.content, 'error');
      break;

    default:
      appendBotMsg(res.content || JSON.stringify(res));
  }
}

/* ════════════════════════════════════════════
   FORMAT PICKER (PDF / CSV choice)
════════════════════════════════════════════ */
function appendFormatPicker(message, symbol, dataType) {
  const time = nowTime();
  const html = `
    <div class="msg-row bot-row" style="animation:msgSlideIn 0.3s ease">
      <div class="msg-avatar bot-avatar"><i class="bi bi-robot"></i></div>
      <div class="msg-bubble bot-bubble">
        <div class="msg-text">
          ${escapeHtml(message)}
          <div class="format-picker">
            <button class="format-btn pdf-btn" onclick="chooseFormat('${symbol}','${dataType}','pdf')">
              <i class="bi bi-file-earmark-pdf-fill"></i> PDF Report
            </button>
            <button class="format-btn csv-btn" onclick="chooseFormat('${symbol}','${dataType}','csv')">
              <i class="bi bi-filetype-csv"></i> CSV Export
            </button>
          </div>
        </div>
        <div class="msg-time">${time}</div>
      </div>
    </div>`;
  $('#chatMessages').append(html);
  scrollToBottom();
}

/* ════════════════════════════════════════════
   FORMAT CHOSEN → GENERATE REPORT
════════════════════════════════════════════ */
function chooseFormat(symbol, dataType, fmt) {
  /* Disable both buttons once chosen */
  $('.format-btn').prop('disabled', true).css('opacity', 0.5);

  const fmtLabel = fmt.toUpperCase();
  appendUserMsg(`${fmtLabel} please`);
  setLoading(true);

  /* Trigger export */
  const url = `/export/?symbol=${encodeURIComponent(symbol)}&data_type=${encodeURIComponent(dataType)}&fmt=${fmt}`;

  /* Check the export exists first with HEAD, then give download link */
  $.ajax({
    url: url,
    type: 'GET',
    success: function () {
      appendDownloadMsg(symbol, dataType, fmt, url);
    },
    error: function (xhr) {
      if (xhr.status === 200) {
        appendDownloadMsg(symbol, dataType, fmt, url);
      } else {
        const detail = xhr.responseJSON?.detail || 'Could not generate report.';
        appendBotMsg(`❌ ${detail}`, 'error');
      }
    },
    complete: function () {
      setLoading(false);
    }
  });
}

function appendDownloadMsg(symbol, dataType, fmt, url) {
  const label = dataType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const icon  = fmt === 'pdf' ? 'bi-file-earmark-pdf-fill' : 'bi-filetype-csv';
  const time  = nowTime();
  const html  = `
    <div class="msg-row bot-row" style="animation:msgSlideIn 0.3s ease">
      <div class="msg-avatar bot-avatar"><i class="bi bi-robot"></i></div>
      <div class="msg-bubble bot-bubble">
        <div class="msg-text">
          ✅ Your <strong>${label}</strong> report for <strong>${symbol}</strong> is ready!
          <br>
          <a class="download-btn" href="${url}" download>
            <i class="bi ${icon}"></i> Download ${fmt.toUpperCase()}
          </a>
        </div>
        <div class="msg-time">${time}</div>
      </div>
    </div>`;
  $('#chatMessages').append(html);
  scrollToBottom();
}

/* ════════════════════════════════════════════
   CLEAR CHAT
════════════════════════════════════════════ */
function clearChat() {
  $('#chatMessages').empty();
  pendingExport = null;
  appendBotMsg('Chat cleared! Ask me about any DSE symbol.', '', true);
}

/* ════════════════════════════════════════════
   SIDEBAR TOGGLE
════════════════════════════════════════════ */
function toggleSidebar() {
  const sb = $('#sidebar');
  if (window.innerWidth <= 768) {
    sb.toggleClass('open');
  } else {
    sb.toggleClass('collapsed');
  }
}

/* ════════════════════════════════════════════
   HELPERS
════════════════════════════════════════════ */

function appendUserMsg(text) {
  const time = nowTime();
  const html = `
    <div class="msg-row user-row">
      <div class="msg-avatar user-avatar"><i class="bi bi-person-fill"></i></div>
      <div class="msg-bubble user-bubble">
        <div class="msg-text">${escapeHtml(text)}</div>
        <div class="msg-time">${time}</div>
      </div>
    </div>`;
  $('#chatMessages').append(html);
  scrollToBottom();
}

function appendBotMsg(text, type = '', noAvatar = false) {
  const time      = nowTime();
  const extraClass = type === 'error' ? 'error-bubble' : '';
  const formattedText = formatMarkdown(text);
  const html = `
    <div class="msg-row bot-row">
      ${noAvatar ? '<div style="width:34px;flex-shrink:0"></div>' : '<div class="msg-avatar bot-avatar"><i class="bi bi-robot"></i></div>'}
      <div class="msg-bubble bot-bubble ${extraClass}">
        <div class="msg-text">${formattedText}</div>
        <div class="msg-time">${time}</div>
      </div>
    </div>`;
  $('#chatMessages').append(html);
  scrollToBottom();
}

function setLoading(state) {
  isBusy = state;
  $('#sendBtn').prop('disabled', state);
  if (state) {
    $('#typingIndicator').removeClass('d-none');
  } else {
    $('#typingIndicator').addClass('d-none');
  }
}

function scrollToBottom() {
  const el = document.getElementById('chatMessages');
  el.scrollTop = el.scrollHeight;
}

function nowTime() {
  return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* Very light markdown → HTML (bold, italic, newlines) */
function formatMarkdown(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,     '<em>$1</em>')
    .replace(/`(.+?)`/g,       '<code style="background:rgba(255,255,255,0.08);padding:1px 5px;border-radius:4px;font-family:monospace;font-size:12px">$1</code>')
    .replace(/\n/g,            '<br>');
}
