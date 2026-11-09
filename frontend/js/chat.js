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
      pendingExport = { symbol: res.symbol, data_type: res.data_type, report_id: res.report_id };
      appendFormatPicker(res.content, res.symbol, res.data_type, res.report_id);
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
function appendFormatPicker(message, symbol, dataType, reportId) {
  const time = nowTime();
  const formattedText = formatMarkdown(message);
  const cleanSymbol = (symbol && symbol !== 'null' && symbol !== 'undefined') ? symbol : 'ALL';
  const cleanType = (dataType && dataType !== 'undefined') ? dataType : 'financial_report';
  const rId = reportId || '';
  const html = `
    <div class="msg-row bot-row" style="animation:msgSlideIn 0.3s ease">
      <div class="msg-avatar bot-avatar"><i class="bi bi-robot"></i></div>
      <div class="msg-bubble bot-bubble">
        <div class="msg-text">
          ${formattedText}
          <div class="format-picker mt-3">
            <button class="format-btn pdf-btn" onclick="chooseFormat('${cleanSymbol}','${cleanType}','pdf','${rId}')">
              <i class="bi bi-file-earmark-pdf-fill"></i> Download PDF
            </button>
            <button class="format-btn csv-btn" onclick="chooseFormat('${cleanSymbol}','${cleanType}','csv','${rId}')">
              <i class="bi bi-filetype-csv"></i> Download CSV
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
function chooseFormat(symbol, dataType, fmt, reportId) {
  /* Disable buttons once clicked */
  $('.format-btn').prop('disabled', true).css('opacity', 0.5);

  const fmtLabel = fmt.toUpperCase();
  appendUserMsg(`${fmtLabel} please`);
  setLoading(true);

  /* Build download URL */
  let url = `/export/?symbol=${encodeURIComponent(symbol || 'ALL')}&fmt=${fmt}`;
  if (dataType && dataType !== 'undefined') {
    url += `&data_type=${encodeURIComponent(dataType)}`;
  }
  if (reportId && reportId !== 'undefined' && reportId !== '') {
    url += `&report_id=${encodeURIComponent(reportId)}`;
  }

  /* Trigger file download directly */
  const a = document.createElement('a');
  a.href = url;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  setTimeout(function () {
    setLoading(false);
    appendDownloadMsg(symbol, dataType, fmt, url);
  }, 300);
}

function appendDownloadMsg(symbol, dataType, fmt, url) {
  const label = dataType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const icon  = fmt === 'pdf' ? 'bi-file-earmark-pdf-fill' : 'bi-filetype-csv';
  const time  = nowTime();
  const displayTarget = (symbol === 'ALL' || symbol === 'ALL_SYMBOLS') ? 'All Listed Stocks' : symbol;
  const html  = `
    <div class="msg-row bot-row" style="animation:msgSlideIn 0.3s ease">
      <div class="msg-avatar bot-avatar"><i class="bi bi-robot"></i></div>
      <div class="msg-bubble bot-bubble">
        <div class="msg-text">
          ✅ Your <strong>${label}</strong> report for <strong>${displayTarget}</strong> is downloaded!
          <br>
          <a class="download-btn mt-2 d-inline-block" href="${url}" download>
            <i class="bi ${icon}"></i> Download Again (${fmt.toUpperCase()})
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

/* Rich markdown → HTML (tables, headers, bold, italic, code, lists) */
function formatMarkdown(text) {
  if (!text) return '';
  let str = String(text);

  // 1. Process Markdown tables
  str = str.replace(/((?:^[ \t]*\|.+?\|[ \t]*(?:\r?\n|$))+)/gm, function (match) {
    const lines = match.trim().split(/\r?\n/).filter(l => l.trim().length > 0);
    if (lines.length < 2) return match;

    let html = '<div class="table-responsive my-2"><table class="table table-sm table-bordered table-dark align-middle mb-0" style="font-size:12.5px;background:rgba(255,255,255,0.03);border-color:rgba(255,255,255,0.12)">';
    let isHeader = true;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      // Skip separator row e.g. |:---|:---|
      if (/^\|[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|$/.test(line)) {
        isHeader = false;
        continue;
      }

      const cells = line.split('|').slice(1, -1);
      if (isHeader) {
        html += '<thead style="background:rgba(30,111,255,0.22);color:#93c5fd"><tr>';
        cells.forEach(c => {
          html += `<th style="padding:6px 10px;border-color:rgba(255,255,255,0.15)">${c.trim()}</th>`;
        });
        html += '</tr></thead><tbody>';
      } else {
        html += '<tr>';
        cells.forEach(c => {
          html += `<td style="padding:5px 10px;border-color:rgba(255,255,255,0.08)">${c.trim()}</td>`;
        });
        html += '</tr>';
      }
    }

    html += '</tbody></table></div>';
    return html;
  });

  // 2. Headings: ### Title or ## Title
  str = str.replace(/^###[ \t]+(.*?)$/gm, '<h6 class="mt-3 mb-1 text-info font-weight-bold">$1</h6>');
  str = str.replace(/^##[ \t]+(.*?)$/gm, '<h5 class="mt-3 mb-2 text-primary font-weight-bold">$1</h5>');

  // 3. Bullet points: * Item or - Item
  str = str.replace(/^[ \t]*[\*\-][ \t]+(.*?)$/gm, '<div style="padding-left:14px;position:relative"><span style="position:absolute;left:0;color:#60a5fa">•</span>$1</div>');

  // 4. Inline elements
  str = str
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,     '<em>$1</em>')
    .replace(/`(.+?)`/g,       '<code style="background:rgba(255,255,255,0.08);padding:1px 5px;border-radius:4px;font-family:monospace;font-size:12px">$1</code>')
    .replace(/\n\n/g,          '<br><br>')
    .replace(/\n/g,            '<br>');

  return str;
}
