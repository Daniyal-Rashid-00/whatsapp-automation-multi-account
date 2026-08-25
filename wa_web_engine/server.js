const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const fs = require('fs');
const path = require('path');
const http = require('http');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');

const PORT = process.env.PORT || 3000;
const WEBHOOK_URL = process.env.WEBHOOK_URL || 'http://127.0.0.1:8000/webhook';

const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Bulletproof crash protection
process.on('uncaughtException', (err) => {
  console.warn('⚠️ [CyberSolu Web Engine] Uncaught exception safely handled:', err?.message || err);
});

process.on('unhandledRejection', (reason) => {
  console.warn('⚠️ [CyberSolu Web Engine] Unhandled promise rejection safely handled:', reason?.message || reason);
});

// Map of sessionName -> sessionObj: { name, status, qr, phone, client, error }
const sessionsMap = new Map();

async function sendWebhookPayload(eventData) {
  try {
    const data = JSON.stringify(eventData);
    const url = new URL(WEBHOOK_URL);
    const req = http.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data)
      }
    });
    req.on('error', () => {});
    req.write(data);
    req.end();
  } catch (e) {}
}

function formatChatId(target) {
  if (!target) return null;
  target = String(target).trim();
  if (target.endsWith('@c.us') || target.endsWith('@g.us') || target.endsWith('@lid') || target.endsWith('@newsletter')) {
    return target;
  }
  if (target.endsWith('@s.whatsapp.net')) {
    return target.replace('@s.whatsapp.net', '@c.us');
  }
  if (target.includes('@')) {
    const parts = target.split('@');
    const user = parts[0].replace(/[^0-9]/g, '');
    const domain = parts[1];
    if (domain === 'lid') {
      return `${user}@lid`;
    }
    return user ? `${user}@c.us` : null;
  }
  const clean = target.replace(/[^0-9]/g, '');
  if (!clean) return null;
  return `${clean}@c.us`;
}

const sessionStartingLocks = new Map();

async function startWWebSession(sessionName = 'default', forceNew = false) {
  if (sessionStartingLocks.has(sessionName)) {
    return sessionStartingLocks.get(sessionName);
  }

  const startPromise = (async () => {
    const sessionsDir = path.join(__dirname, 'sessions');
    if (!fs.existsSync(sessionsDir)) {
      fs.mkdirSync(sessionsDir, { recursive: true });
    }

    const sessionDataDir = path.join(sessionsDir, `session-${sessionName}`);

    let sessionObj = sessionsMap.get(sessionName);

    if (forceNew) {
      if (sessionObj && sessionObj.client) {
        try { await sessionObj.client.destroy(); } catch (e) {}
        sessionObj.client = null;
      }
      try { fs.rmSync(sessionDataDir, { recursive: true, force: true }); } catch (e) {}
      sessionsMap.delete(sessionName);
      sessionObj = null;
    }

    // GUARD: If session is already starting, waiting for QR, or connected, do NOT re-create client
    if (sessionObj && (sessionObj.status === 'STARTING' || sessionObj.status === 'SCAN_QR_CODE' || sessionObj.status === 'WORKING')) {
      return sessionObj;
    }

    if (!sessionObj) {
      sessionObj = {
        name: sessionName,
        status: 'STARTING',
        qr: null,
        phone: null,
        client: null,
        error: null
      };
      sessionsMap.set(sessionName, sessionObj);
    } else {
      sessionObj.status = 'STARTING';
      sessionObj.error = null;
    }

    sendWebhookPayload({
      event: 'session.status',
      session: sessionName,
      payload: { status: 'STARTING', session: sessionName }
    });

    console.log(`🚀 [${sessionName}] Launching WhatsApp Web client in visible Chromium...`);

    // Clean crash locks and session restore state so Chromium launches cleanly after sudden power outage / crash
    const profileDir = path.join(sessionsDir, `session-${sessionName}`);
    const sessionRestoreDir = path.join(profileDir, 'Default', 'Sessions');
    try {
      if (fs.existsSync(sessionRestoreDir)) {
        fs.rmSync(sessionRestoreDir, { recursive: true, force: true });
      }
      const singletonLock = path.join(profileDir, 'SingletonLock');
      if (fs.existsSync(singletonLock)) {
        fs.rmSync(singletonLock, { force: true });
      }
      const singletonCookie = path.join(profileDir, 'SingletonCookie');
      if (fs.existsSync(singletonCookie)) {
        fs.rmSync(singletonCookie, { force: true });
      }
    } catch (e) {}

    const client = new Client({
      authStrategy: new LocalAuth({
        clientId: sessionName,
        dataPath: sessionsDir
      }),
      takeoverOnConflict: true,
      takeoverTimeoutMs: 1000,
      puppeteer: {
        headless: false,
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-dev-shm-usage',
          '--disable-accelerated-2d-canvas',
          '--no-first-run',
          '--no-zygote',
          '--disable-gpu',
          '--disable-background-timer-throttling',
          '--disable-backgrounding-occluded-windows',
          '--disable-renderer-backgrounding',
          '--disable-ipc-flooding-protection',
          '--no-restore-session-state',
          '--disable-session-crashed-bubble',
          '--hide-crash-restore-bubble',
          '--no-default-browser-check'
        ]
      }
    });

    sessionObj.client = client;

    // Helper: Closes any extra/duplicate restored tabs in Chromium so only 1 single tab remains
    const enforceSingleTab = async () => {
      if (client.pupBrowser) {
        try {
          const pages = await client.pupBrowser.pages();
          if (pages.length > 1) {
            const primaryPage = client.pupPage || pages[0];
            for (const p of pages) {
              if (p !== primaryPage) {
                try { await p.close(); } catch (e) {}
              }
            }
          }
        } catch (e) {}
      }
    };

    client.on('qr', async (qr) => {
      if (sessionObj.client !== client) return;
      enforceSingleTab();
      try {
        const qrDataUrl = await QRCode.toDataURL(qr, { margin: 2, scale: 8 });
        sessionObj.qr = qrDataUrl;
        sessionObj.status = 'SCAN_QR_CODE';
        console.log(`📸 [${sessionName}] QR code generated. Ready for scan in UI.`);
        sendWebhookPayload({
          event: 'session.status',
          session: sessionName,
          payload: { status: 'SCAN_QR_CODE', session: sessionName, qr: qrDataUrl }
        });
      } catch (err) {
        console.error(`❌ [${sessionName}] QR conversion error:`, err);
      }
    });

    client.on('authenticated', () => {
      if (sessionObj.client !== client) return;
      enforceSingleTab();
      console.log(`🔐 [${sessionName}] WhatsApp Authenticated successfully!`);
      sessionObj.status = 'STARTING';
      sessionObj.qr = null;
    });

    client.on('auth_failure', (msg) => {
      if (sessionObj.client !== client) return;
      console.error(`❌ [${sessionName}] WhatsApp Authentication failure:`, msg);
      sessionObj.status = 'STOPPED';
      sessionObj.error = String(msg);
      sessionObj.qr = null;
      sendWebhookPayload({
        event: 'session.status',
        session: sessionName,
        payload: { status: 'STOPPED', session: sessionName, error: msg }
      });
    });

    client.on('ready', async () => {
      if (sessionObj.client !== client) return;
      await enforceSingleTab();
      const widUser = (client.info && client.info.wid && client.info.wid.user) ? client.info.wid.user : '';
      sessionObj.status = 'WORKING';
      sessionObj.phone = widUser;
      sessionObj.qr = null;
      sessionObj.error = null;

      console.log(`✅ [${sessionName}] WhatsApp session ready & operational! Phone: ${widUser}`);

      sendWebhookPayload({
        event: 'session.status',
        session: sessionName,
        payload: { status: 'WORKING', session: sessionName, phone: widUser }
      });
    });

    client.on('disconnected', (reason) => {
      if (sessionObj.client !== client) return;
      console.warn(`⚠️ [${sessionName}] WhatsApp disconnected:`, reason);
      sessionObj.status = 'STOPPED';
      sessionObj.qr = null;
      sessionObj.error = String(reason);

      sendWebhookPayload({
        event: 'session.status',
        session: sessionName,
        payload: { status: 'STOPPED', session: sessionName, reason }
      });

      if (reason !== 'LOGOUT') {
        console.log(`🔄 [${sessionName}] Auto-reconnecting in 5s...`);
        setTimeout(() => {
          if (sessionObj.status === 'STOPPED') {
            startWWebSession(sessionName, false).catch(() => {});
          }
        }, 5000);
      }
    });

    // Message Deduplication cache to prevent duplicate webhooks
    const processedMsgIds = new Set();
    setInterval(() => {
      if (processedMsgIds.size > 2000) {
        processedMsgIds.clear();
      }
    }, 60000);

    // Unified Message Handler: Captures 100% of messages (saved contacts, active chats, background sync, incoming & outgoing)
    const handleAnyMessage = async (msg) => {
      try {
        if (!msg) return;
        const messageId = (msg.id && msg.id._serialized) ? msg.id._serialized : ((msg.id && msg.id.id) ? msg.id.id : String(Date.now()));
        
        // Prevent duplicate processing
        if (processedMsgIds.has(messageId)) return;
        processedMsgIds.add(messageId);

        const fromJid = msg.from || '';
        const toJid = msg.to || '';
        const isFromMe = Boolean(msg.fromMe);

        // Skip status broadcast and groups
        if (fromJid.endsWith('@g.us') || toJid.endsWith('@g.us') || fromJid.includes('@broadcast') || fromJid === 'status@broadcast') return;

        // Skip archived chats completely (respect user's manual archive organization)
        try {
          const chat = await msg.getChat();
          if (chat && chat.archived) {
            console.log(`🗂️ [${sessionName}] Skipping message from archived chat: ${fromJid || toJid}`);
            return;
          }
        } catch (e) {}

        const body = msg.body || '';
        const hasMedia = Boolean(msg.hasMedia);
        if (!body && !hasMedia) return;

        // Skip inbound media-only messages (voice notes, images, stickers, videos with NO text caption)
        // This saves CPU, SQLite queue writes, and AI token costs.
        if (!isFromMe && !body.trim() && hasMedia) {
          console.log(`📷 [${sessionName}] Skipping inbound media-only message (no text) from ${fromJid}`);
          return;
        }

        const timestamp = msg.timestamp || Math.floor(Date.now() / 1000);
        const nowSec = Math.floor(Date.now() / 1000);

        // Skip historical messages synced from phone during startup (older than 60 seconds)
        // Ensures each new session starts completely fresh with 0 backlog
        if (nowSec - Number(timestamp) > 60) {
          console.log(`⌛ [${sessionName}] Skipping historical synced message (${nowSec - Number(timestamp)}s old): ${messageId}`);
          return;
        }

        if (isFromMe) {
          // Outbound message sent by human from phone/web -> triggers Human Takeover in backend
          const customerPhone = toJid.split('@')[0];
          console.log(`📤 [${sessionName}] Outbound message to ${toJid}: "${body.slice(0, 50)}"`);
          sendWebhookPayload({
            event: 'message',
            session: sessionName,
            payload: {
              id: messageId,
              session: sessionName,
              from: fromJid,
              to: toJid,
              chatId: toJid,
              phone: customerPhone,
              body: body,
              fromMe: true,
              timestamp: timestamp,
              hasMedia: hasMedia
            }
          });
        } else {
          // Inbound customer message (saved contacts, @lid, @c.us, active chats)
          const senderPhone = fromJid.split('@')[0];
          let pushName = senderPhone;
          try {
            const contact = await msg.getContact();
            if (contact && (contact.pushname || contact.name || contact.verifiedName)) {
              pushName = contact.pushname || contact.name || contact.verifiedName;
            }
          } catch (e) {}

          console.log(`📩 [${sessionName}] Inbound message from ${pushName} (${fromJid}): "${body.slice(0, 80)}"`);
          sendWebhookPayload({
            event: 'message',
            session: sessionName,
            payload: {
              id: messageId,
              session: sessionName,
              from: fromJid,
              chatId: fromJid,
              phone: senderPhone,
              name: pushName,
              body: body,
              fromMe: false,
              timestamp: timestamp,
              hasMedia: hasMedia
            }
          });
        }
      } catch (err) {
        console.warn(`⚠️ [${sessionName}] Error handling message:`, err?.message);
      }
    };

    client.on('message_create', handleAnyMessage);
    client.on('message', handleAnyMessage);

    try {
      client.initialize().catch(err => {
        console.error(`❌ [${sessionName}] client.initialize() error:`, err?.message || err);
        sessionObj.status = 'STOPPED';
        sessionObj.error = err?.message || String(err);
      });
    } catch (err) {
      console.error(`❌ [${sessionName}] Launch exception:`, err);
      sessionObj.status = 'STOPPED';
      sessionObj.error = err?.message || String(err);
    }

    return sessionObj;
  })();

  sessionStartingLocks.set(sessionName, startPromise);
  try {
    return await startPromise;
  } finally {
    sessionStartingLocks.delete(sessionName);
  }
}

// REST Endpoints

app.get('/', (req, res) => {
  res.json({ app: 'CyberSolu Auto — WhatsApp Web Engine', status: 'OK', activeSessions: sessionsMap.size });
});

app.get('/health', (req, res) => {
  const sessionName = req.query.session || 'default';
  const sessionObj = sessionsMap.get(sessionName);
  res.json({ status: 'OK', session: sessionObj ? sessionObj.status : 'STOPPED' });
});

app.get('/api/qr', async (req, res) => {
  const sessionName = req.query.session || 'default';
  let sessionObj = sessionsMap.get(sessionName);

  if (!sessionObj || sessionObj.status === 'STOPPED') {
    try {
      sessionObj = await startWWebSession(sessionName, false);
    } catch (e) {}
  }

  res.json({
    status: sessionObj ? sessionObj.status : 'STOPPED',
    qr: sessionObj ? sessionObj.qr : null
  });
});

app.get('/api/sessions', (req, res) => {
  const list = [];
  sessionsMap.forEach((val, key) => {
    list.push({
      session: key,
      status: val.status,
      phone: val.phone || '',
      error: val.error
    });
  });
  res.json(list);
});

app.post('/api/sessions/start', async (req, res) => {
  const sessionName = req.body.session || 'default';
  const forceNew = Boolean(req.body.scan_qr || req.body.force_new);
  try {
    const sessionObj = await startWWebSession(sessionName, forceNew);
    res.json({ status: sessionObj ? sessionObj.status : 'STARTING', session: sessionName });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/sessions/repair', async (req, res) => {
  const sessionName = req.body.session || 'default';
  try {
    const sessionObj = sessionsMap.get(sessionName);
    if (sessionObj && sessionObj.client) {
      try { await sessionObj.client.destroy(); } catch (e) {}
      sessionsMap.delete(sessionName);
    }
    const newSessionObj = await startWWebSession(sessionName, false);
    res.json({ status: 'REPAIRED', session: sessionName });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/sessions/logout', async (req, res) => {
  const sessionName = req.body.session || 'default';
  const sessionObj = sessionsMap.get(sessionName);

  if (sessionObj && sessionObj.client) {
    try { await sessionObj.client.logout(); } catch (e) {}
    try { await sessionObj.client.destroy(); } catch (e) {}
  }

  const sessionDataDir = path.join(__dirname, 'sessions', `session-${sessionName}`);
  try { fs.rmSync(sessionDataDir, { recursive: true, force: true }); } catch (e) {}

  if (sessionObj) {
    sessionObj.status = 'STOPPED';
    sessionObj.qr = null;
    sessionObj.client = null;
    sessionObj.phone = null;
    sessionObj.error = 'Logged out';
  }

  sendWebhookPayload({
    event: 'session.status',
    session: sessionName,
    payload: { status: 'STOPPED', session: sessionName }
  });

  res.json({ status: 'LOGGED_OUT', session: sessionName });
});

app.delete('/api/sessions/:session', async (req, res) => {
  const sessionName = req.params.session;
  const sessionObj = sessionsMap.get(sessionName);

  if (sessionObj && sessionObj.client) {
    try { await sessionObj.client.destroy(); } catch (e) {}
  }

  const sessionDataDir = path.join(__dirname, 'sessions', `session-${sessionName}`);
  try { fs.rmSync(sessionDataDir, { recursive: true, force: true }); } catch (e) {}

  sessionsMap.delete(sessionName);

  sendWebhookPayload({
    event: 'session.status',
    session: sessionName,
    payload: { status: 'DELETED', session: sessionName }
  });

  res.json({ status: 'DELETED', session: sessionName });
});

app.post('/api/sendText', async (req, res) => {
  try {
    const { chatId, phone, text, session } = req.body;
    const sessionName = session || 'default';
    const targetJid = formatChatId(chatId || phone);

    const sessionObj = sessionsMap.get(sessionName);
    if (!targetJid || !text) {
      return res.status(400).json({ error: 'Missing target chatId/phone or text' });
    }

    if (!sessionObj || sessionObj.status !== 'WORKING' || !sessionObj.client) {
      return res.status(503).json({ error: `WhatsApp session [${sessionName}] not connected` });
    }

    const sent = await sessionObj.client.sendMessage(targetJid, text);
    const sentId = (sent && sent.id && sent.id._serialized) ? sent.id._serialized : ((sent && sent.id && sent.id.id) ? sent.id.id : 'OK');
    console.log(`📤 [${sessionName}] Message dispatched to ${targetJid}: "${text.slice(0, 30)}..."`);
    res.json({ status: 'SUCCESS', id: sentId });
  } catch (err) {
    console.error('❌ Error sending message:', err.message);
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/sendFile', async (req, res) => {
  try {
    const { chatId, phone, caption, file_path, filePath, file, filename, session } = req.body;
    const sessionName = session || 'default';
    const targetJid = formatChatId(chatId || phone);
    const targetPath = file_path || filePath;

    const sessionObj = sessionsMap.get(sessionName);
    if (!targetJid) {
      return res.status(400).json({ error: 'Missing target chatId or phone' });
    }

    if (!sessionObj || sessionObj.status !== 'WORKING' || !sessionObj.client) {
      return res.status(503).json({ error: `WhatsApp session [${sessionName}] not connected` });
    }

    let media = null;

    if (file && file.data) {
      const mimetype = file.mimetype || 'application/octet-stream';
      media = new MessageMedia(mimetype, file.data, filename || file.filename || 'file');
    } else if (targetPath && fs.existsSync(targetPath)) {
      media = MessageMedia.fromFilePath(targetPath);
      if (filename) media.filename = filename;
    }

    if (media) {
      const sent = await sessionObj.client.sendMessage(targetJid, media, { caption: caption || '' });
      const sentId = (sent && sent.id && sent.id._serialized) ? sent.id._serialized : ((sent && sent.id && sent.id.id) ? sent.id.id : 'OK');
      console.log(`📎 [${sessionName}] Media attachment dispatched to ${targetJid}`);
      return res.json({ status: 'SUCCESS', id: sentId });
    }

    if (caption) {
      const sent = await sessionObj.client.sendMessage(targetJid, caption);
      const sentId = (sent && sent.id && sent.id._serialized) ? sent.id._serialized : ((sent && sent.id && sent.id.id) ? sent.id.id : 'OK');
      return res.json({ status: 'SUCCESS', id: sentId });
    }

    res.status(400).json({ error: 'File path or data not found' });
  } catch (err) {
    console.error('❌ Error sending file:', err.message);
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/shutdown', async (req, res) => {
  console.log('🛑 Received shutdown request. Closing all active WhatsApp Web browser instances...');
  res.json({ status: 'SHUTTING_DOWN' });
  setTimeout(async () => {
    for (const [sName, sessionObj] of sessionsMap.entries()) {
      if (sessionObj && sessionObj.client) {
        try {
          console.log(`Closing browser for [${sName}]...`);
          await sessionObj.client.destroy();
        } catch (e) {}
      }
    }
    process.exit(0);
  }, 200);
});

// Start Express Server & Auto-Restore All Saved Sessions
app.listen(PORT, () => {
  console.log(`🚀 CyberSolu WhatsApp Web Engine (whatsapp-web.js) running on http://localhost:${PORT}`);
  const sessionsDir = path.join(__dirname, 'sessions');
  if (fs.existsSync(sessionsDir)) {
    const folders = fs.readdirSync(sessionsDir);
    for (const folder of folders) {
      if (folder.startsWith('session-')) {
        const sessionName = folder.replace('session-', '');
        console.log(`🔄 Auto-starting saved WhatsApp Web session: [${sessionName}]...`);
        startWWebSession(sessionName, false).catch(err => {
          console.error(`Failed to start session [${sessionName}]:`, err);
        });
      }
    }
  }
});
