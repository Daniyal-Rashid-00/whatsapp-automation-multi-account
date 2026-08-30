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
          '--no-default-browser-check',
          '--js-flags=--max-old-space-size=384',
          '--disable-extensions',
          '--disable-background-networking',
          '--disable-sync',
          '--disable-default-apps',
          '--disable-translate',
          '--metrics-recording-only'
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
        const body = msg.body || '';

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

        const msgType = String(msg.type || '').toLowerCase();
        const isVoice = msgType === 'ptt' || msgType === 'audio' || msgType === 'voice';
        let hasMedia = Boolean(msg.hasMedia) || isVoice;
        let audioBase64 = null;
        let audioMime = null;

        // If it's an inbound voice note / audio, download the media payload for Gemini AI
        if (!isFromMe && isVoice) {
          msg.hasMedia = true; // Overwrite false directPath on PTT messages
          for (let attempt = 1; attempt <= 4; attempt++) {
            try {
              console.log(`🎙️ [${sessionName}] Downloading incoming voice note from ${fromJid} (attempt ${attempt}/4)...`);
              let media = null;
              try {
                media = await msg.downloadMedia();
              } catch (e) {}

              // Direct page evaluate fallback if helper returned null/undefined
              if ((!media || !media.data) && sessionObj.client && sessionObj.client.pupPage) {
                try {
                  const evalResult = await sessionObj.client.pupPage.evaluate(async (rawMsgId, targetChatId) => {
                    const logs = [];
                    try {
                      const collections = window.require ? window.require('WAWebCollections') : null;
                      if (!collections) return { error: 'WAWebCollections not available', logs };
                      
                      const cleanId = String(rawMsgId);
                      const shortId = cleanId.split('_').pop(); // e.g. AC45FC18DBC9B7C6B066F2FCE5BD675A

                      let m = null;
                      // 1. Search in global Msg collection
                      if (collections.Msg) {
                        m = collections.Msg.get(cleanId) || collections.Msg.get(shortId);
                        if (!m && collections.Msg.getModelsArray) {
                          m = collections.Msg.getModelsArray().find(x => {
                            const sid = x.id ? (x.id._serialized || x.id.id || String(x.id)) : '';
                            return sid === cleanId || sid.includes(shortId);
                          });
                        }
                      }

                      // 2. Search in Chat msgs
                      if (!m && collections.Chat && targetChatId) {
                        const chat = collections.Chat.get(targetChatId) || (collections.Chat.getModelsArray && collections.Chat.getModelsArray().find(c => String(c.id).includes(targetChatId)));
                        if (chat && chat.msgs) {
                          const chatMsgs = chat.msgs.getModelsArray ? chat.msgs.getModelsArray() : (chat.msgs.models || []);
                          m = chatMsgs.find(x => {
                            const sid = x.id ? (x.id._serialized || x.id.id || String(x.id)) : '';
                            return sid === cleanId || sid.includes(shortId);
                          });
                        }
                      }

                      if (!m) {
                        return { error: `Msg model not found for ${cleanId} (shortId: ${shortId})`, logs };
                      }

                      logs.push(`Found msg model: type=${m.type}, hasMedia=${Boolean(m.mediaData)}`);

                      // 3. Try to download media if needed
                      if (m.downloadMedia && m.mediaData && m.mediaData.mediaStage !== 'RESOLVED') {
                        try {
                          await m.downloadMedia({ downloadEvenIfExpensive: true, rmrReason: 1 });
                          logs.push(`downloadMedia called, new stage=${m.mediaData?.mediaStage}`);
                        } catch (e) {
                          logs.push(`downloadMedia err: ${e.message}`);
                        }
                      }

                      // 4. Try to fetch directly from renderableUrl / blob
                      if (m.mediaData && m.mediaData.renderableUrl) {
                        try {
                          const resp = await fetch(m.mediaData.renderableUrl);
                          const buffer = await resp.arrayBuffer();
                          if (buffer && buffer.byteLength > 0 && window.WWebJS && window.WWebJS.arrayBufferToBase64Async) {
                            const b64 = await window.WWebJS.arrayBufferToBase64Async(buffer);
                            return { data: b64, mimetype: m.mimetype || m.mediaData.mimetype || 'audio/ogg', logs };
                          }
                        } catch (e) {
                          logs.push(`renderableUrl fetch err: ${e.message}`);
                        }
                      }

                      // 5. Fallback to downloadManager.downloadAndMaybeDecrypt
                      const dm = window.require ? window.require('WAWebDownloadManager') : null;
                      if (dm && dm.downloadManager) {
                        const mediaData = m.mediaData || {};
                        const decryptedMedia = await dm.downloadManager.downloadAndMaybeDecrypt({
                          directPath: m.directPath || mediaData.directPath,
                          encFilehash: m.encFilehash || mediaData.encFilehash,
                          filehash: m.filehash || mediaData.filehash,
                          mediaKey: m.mediaKey || mediaData.mediaKey,
                          mediaKeyTimestamp: m.mediaKeyTimestamp || mediaData.mediaKeyTimestamp,
                          type: m.type || 'ptt',
                          signal: new AbortController().signal,
                          downloadQpl: {
                            addAnnotations: function () { return this; },
                            addPoint: function () { return this; }
                          }
                        });

                        if (decryptedMedia && window.WWebJS && window.WWebJS.arrayBufferToBase64Async) {
                          const b64 = await window.WWebJS.arrayBufferToBase64Async(decryptedMedia);
                          return { data: b64, mimetype: m.mimetype || mediaData.mimetype || 'audio/ogg', logs };
                        }
                      }

                      return { error: 'No media extracted after all fallbacks', logs };
                    } catch (e) {
                      return { error: `Exception in evaluate: ${e.message}`, logs };
                    }
                  }, messageId, fromJid);

                  if (evalResult && evalResult.data) {
                    media = { data: evalResult.data, mimetype: evalResult.mimetype };
                  } else if (evalResult && evalResult.error) {
                    console.log(`🎙️ [${sessionName}] Audio extraction detail: ${evalResult.error} | logs: ${JSON.stringify(evalResult.logs)}`);
                  }
                } catch (e) {
                  console.warn(`⚠️ [${sessionName}] Evaluate execution error: ${e.message}`);
                }
              }

              if (media && media.data) {
                audioBase64 = media.data;
                audioMime = media.mimetype ? media.mimetype.split(';')[0] : 'audio/ogg';
                console.log(`🎙️ [${sessionName}] Voice note downloaded successfully (${Math.round(audioBase64.length / 1024)} KB, ${audioMime})`);
                break;
              }
            } catch (e) {
              console.warn(`⚠️ [${sessionName}] Could not download voice note (attempt ${attempt}): ${e?.message || e}`);
            }
            await new Promise(r => setTimeout(r, 600));
          }
        }

        // Skip inbound non-voice media-only messages (silent images, stickers, videos with NO text caption)
        if (!isFromMe && !body.trim() && hasMedia && !isVoice) {
          console.log(`📷 [${sessionName}] Skipping inbound media-only message (no text, non-voice) from ${fromJid}`);
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
              hasMedia: hasMedia,
              type: msgType,
              isVoice: isVoice
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

          const displayBody = body || (isVoice ? '🎤 [Voice Note]' : '');
          console.log(`📩 [${sessionName}] Inbound message from ${pushName} (${fromJid}): "${displayBody.slice(0, 80)}" (isVoice: ${isVoice})`);
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
              body: displayBody,
              fromMe: false,
              timestamp: timestamp,
              hasMedia: hasMedia,
              type: msgType,
              isVoice: isVoice,
              mediaData: audioBase64,
              mimeType: audioMime
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

app.get('/api/debug/msg', async (req, res) => {
  const sessionName = req.query.session || 'default';
  const msgId = req.query.msgId;
  const sessionObj = sessionsMap.get(sessionName);
  if (!sessionObj || !sessionObj.client || !sessionObj.client.pupPage) {
    return res.status(503).json({ error: 'Session not active' });
  }

  try {
    const diag = await sessionObj.client.pupPage.evaluate(async (targetId) => {
      const collections = window.require ? window.require('WAWebCollections') : null;
      if (!collections || !collections.Msg) return { error: 'WAWebCollections not available' };
      
      const allMsgs = collections.Msg.getModelsArray ? collections.Msg.getModelsArray() : (collections.Msg.models || []);
      const pttMsgs = allMsgs.filter(m => m.type === 'ptt' || m.type === 'audio' || (m.mediaData && m.mediaData.type === 'ptt')).slice(-5);
      
      const summary = pttMsgs.map(m => ({
        id: m.id ? (m.id._serialized || m.id) : null,
        type: m.type,
        mimetype: m.mimetype,
        directPath: m.directPath,
        mediaData: m.mediaData ? {
          type: m.mediaData.type,
          mediaStage: m.mediaData.mediaStage,
          directPath: m.mediaData.directPath,
          renderableUrl: m.mediaData.renderableUrl,
          mimetype: m.mediaData.mimetype,
          filehash: m.mediaData.filehash ? 'present' : 'none',
          mediaKey: m.mediaData.mediaKey ? 'present' : 'none'
        } : null
      }));

      // Test downloading the last PTT message
      let testDownload = null;
      let downloadError = null;
      if (pttMsgs.length > 0) {
        const lastMsg = pttMsgs[pttMsgs.length - 1];
        try {
          if (lastMsg.downloadMedia && lastMsg.mediaData && lastMsg.mediaData.mediaStage !== 'RESOLVED') {
            await lastMsg.downloadMedia({ downloadEvenIfExpensive: true, rmrReason: 1 });
          }
          const dm = window.require ? window.require('WAWebDownloadManager') : null;
          if (dm && dm.downloadManager) {
            const md = lastMsg.mediaData || {};
            const buf = await dm.downloadManager.downloadAndMaybeDecrypt({
              directPath: lastMsg.directPath || md.directPath,
              encFilehash: lastMsg.encFilehash || md.encFilehash,
              filehash: lastMsg.filehash || md.filehash,
              mediaKey: lastMsg.mediaKey || md.mediaKey,
              mediaKeyTimestamp: lastMsg.mediaKeyTimestamp || md.mediaKeyTimestamp,
              type: lastMsg.type || 'ptt',
              signal: new AbortController().signal,
              downloadQpl: { addAnnotations: () => {}, addPoint: () => {} }
            });
            if (buf) {
              testDownload = { size: buf.byteLength, status: 'SUCCESS' };
            }
          }
        } catch (e) {
          downloadError = e.message || String(e);
        }
      }

      return {
        totalMsgsInRAM: allMsgs.length,
        pttCount: pttMsgs.length,
        recentPtt: summary,
        testDownload,
        downloadError
      };
    }, msgId);

    res.json(diag);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
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

// =========================================================================
// ON-DEMAND UNREAD CHATS CATCH-UP ENDPOINT
// Direct WhatsApp Web Store extraction for 100% reliability and 0ms speed
// =========================================================================
app.get('/api/unread-messages', async (req, res) => {
  const targetSession = req.query.session || 'all';
  const maxHours = parseFloat(req.query.maxHours) || 0;
  const cutoffTime = maxHours > 0 ? (Math.floor(Date.now() / 1000) - (maxHours * 3600)) : 0;

  const targetSessions = [];
  if (targetSession === 'all') {
    for (const [name, obj] of sessionsMap.entries()) {
      if (obj && obj.client && obj.status === 'WORKING') {
        targetSessions.push({ name, client: obj.client, pupPage: obj.client.pupPage });
      }
    }
  } else {
    const obj = sessionsMap.get(targetSession);
    if (obj && obj.client && obj.status === 'WORKING') {
      targetSessions.push({ name: targetSession, client: obj.client, pupPage: obj.client.pupPage });
    }
  }

  if (targetSessions.length === 0) {
    return res.json({
      success: true,
      totalUnread: 0,
      messages: [],
      note: 'No active WORKING sessions found'
    });
  }

  const allUnread = [];

  for (const { name: sName, client, pupPage } of targetSessions) {
    try {
      if (pupPage) {
        const storeResults = await pupPage.evaluate((cutoff) => {
          const results = [];
          try {
            const getChatModels = () => {
              if (window.Store && window.Store.Chat) {
                return window.Store.Chat.getModelsArray ? window.Store.Chat.getModelsArray() : (window.Store.Chat.models || window.Store.Chat._models || []);
              }
              if (typeof window.require === 'function') {
                try {
                  const col = window.require('WAWebCollections');
                  if (col && col.Chat) {
                    return col.Chat.getModelsArray ? col.Chat.getModelsArray() : (col.Chat.models || col.Chat._models || []);
                  }
                } catch (e) {}
              }
              return [];
            };

            const chatList = getChatModels();

            for (const c of chatList) {
              if (!c || !c.id) continue;
              const jid = c.id._serialized || c.id.user || '';
              if (jid.endsWith('@g.us') || jid.includes('@broadcast') || jid.includes('@newsletter')) continue;

              // Ignore archived chats completely
              if (c.archive === true || c.isArchived === true || c.archived === true || c.archive === 1) continue;

              const unread = Number(c.unreadCount || c.unreadMsgCount || (c.hasUnread ? 1 : 0) || 0);
              const markedUnread = Boolean(c.markedUnread);

              // Only chats with unreadCount > 0 or marked unread
              if (unread <= 0 && !markedUnread) continue;

              // Find the last customer message
              let lastMsg = null;
              const chatMsgs = c.msgs ? (c.msgs.getModelsArray ? c.msgs.getModelsArray() : (c.msgs.models || c.msgs._models || [])) : [];

              for (let i = chatMsgs.length - 1; i >= 0; i--) {
                const m = chatMsgs[i];
                if (m && !m.fromMe && !m.id?.fromMe) {
                  lastMsg = m;
                  break;
                }
              }

              // Fallback to lastReceivedKey
              if (!lastMsg && c.lastReceivedKey && window.Store && window.Store.Msg) {
                try {
                  lastMsg = window.Store.Msg.get(c.lastReceivedKey);
                } catch (e) {}
              }

              let msgTimestamp = c.t || (lastMsg ? (lastMsg.t || lastMsg.timestamp) : 0) || 0;
              if (cutoff > 0 && msgTimestamp > 0 && msgTimestamp < cutoff) {
                continue; // Skip by time cutoff
              }

              let body = '';
              let isVoice = false;
              let msgId = `UNREAD_${c.id._serialized}_${Date.now()}`;

              if (lastMsg) {
                msgId = lastMsg.id ? (lastMsg.id._serialized || lastMsg.id.id || msgId) : msgId;
                body = lastMsg.body || lastMsg.caption || '';
                const mType = String(lastMsg.type || '').toLowerCase();
                isVoice = (mType === 'ptt' || mType === 'audio' || mType === 'voice');
                if (isVoice && !body) {
                  body = '🎤 [Voice Note]';
                }
              } else {
                body = c.previewMessage ? (c.previewMessage.body || c.previewMessage.caption || '') : '';
              }

              const customerName = c.formattedTitle || c.name || (c.contact ? (c.contact.pushname || c.contact.name || '') : '') || '';

              results.push({
                chatId: jid,
                customerName: customerName,
                unreadCount: unread || 1,
                messageId: msgId,
                body: body,
                isVoice: isVoice,
                timestamp: msgTimestamp || Math.floor(Date.now() / 1000)
              });
            }
          } catch (e) {
            results.push({ error: e.message });
          }
          return results;
        }, cutoffTime);

        if (Array.isArray(storeResults)) {
          for (const item of storeResults) {
            if (item && !item.error && item.chatId) {
              allUnread.push({
                session: sName,
                chatId: item.chatId,
                customerName: item.customerName,
                unreadCount: item.unreadCount,
                messageId: item.messageId,
                body: item.body,
                isVoice: item.isVoice,
                timestamp: item.timestamp,
                timeFormatted: new Date(item.timestamp * 1000).toLocaleString()
              });
            }
          }
        }
      }
    } catch (err) {
      console.warn(`⚠️ [${sName}] pupPage.evaluate unread scan error:`, err.message);
    }
  }

  return res.json({
    success: true,
    totalUnread: allUnread.length,
    messages: allUnread
  });
});

app.get('/api/debug/label', async (req, res) => {
  const sessionName = req.query.session || 'default';
  const sessionObj = sessionsMap.get(sessionName);
  if (!sessionObj || !sessionObj.client) return res.status(503).json({ error: 'offline' });
  try {
    const debug = await sessionObj.client.pupPage.evaluate(() => {
      let labelsInfo = [];
      try {
        const collections = window.require('WAWebCollections');
        if (collections && collections.Label) {
          const raw = collections.Label.getModelsArray ? collections.Label.getModelsArray() : collections.Label.models;
          labelsInfo = (raw || []).map(l => {
            const items = l.labelItemCollection ? (l.labelItemCollection.getModelsArray ? l.labelItemCollection.getModelsArray() : (l.labelItemCollection.models || [])) : [];
            return {
              id: l.id,
              name: l.name,
              itemsCount: items.length,
              sampleItem: items[0] ? { parentId: items[0].parentId, parentType: items[0].parentType } : null
            };
          });
        }
      } catch (e) {
        labelsInfo = [{ error: e.message }];
      }
      return {
        hasWAWebCollections: typeof window.require === 'function',
        labelsCount: labelsInfo.length,
        labels: labelsInfo
      };
    });
    res.json(debug);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/debug/test-contact', async (req, res) => {
  const sessionName = req.query.session || 'default';
  const sessionObj = sessionsMap.get(sessionName);
  if (!sessionObj || !sessionObj.client) return res.status(503).json({ error: 'offline' });
  try {
    const testResult = await sessionObj.client.pupPage.evaluate(async () => {
      const collections = window.require('WAWebCollections');
      const label642 = collections.Label.get('642');
      const items = label642 ? (label642.labelItemCollection.getModelsArray ? label642.labelItemCollection.getModelsArray() : label642.labelItemCollection.models) : [];
      const chatItem = items.find(it => it.parentType === 'Chat' && it.parentId);
      if (!chatItem) return { error: 'no chat item found' };

      const jid = String(chatItem.parentId);
      const contactObj = collections.Contact ? collections.Contact.get(jid) : null;
      let resolvedPhone = null;
      try {
        if (window.WWebJS && window.WWebJS.enforceLidAndPnRetrieval) {
          const r = await window.WWebJS.enforceLidAndPnRetrieval(jid);
          resolvedPhone = r?.phone?._serialized || null;
        }
      } catch (e) {
        resolvedPhone = e.message;
      }

      return {
        jid,
        contactObjKeys: contactObj ? Object.keys(contactObj) : [],
        contactPhoneNumber: contactObj?.phoneNumber,
        contactName: contactObj?.name,
        contactPushname: contactObj?.pushname,
        contactIsMyContact: contactObj?.isMyContact,
        contactIsAddressBook: contactObj?.isAddressBookContact,
        resolvedPhone
      };
    });
    res.json(testResult);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/labels', async (req, res) => {
  const sessionName = req.query.session || 'default';
  const sessionObj = sessionsMap.get(sessionName);
  if (!sessionObj || sessionObj.status !== 'WORKING' || !sessionObj.client) {
    return res.status(503).json({ error: `Session [${sessionName}] not connected` });
  }
  try {
    const listData = await sessionObj.client.pupPage.evaluate(() => {
      const out = [];
      try {
        const collections = window.require('WAWebCollections');
        if (collections && collections.Label) {
          const raw = collections.Label.getModelsArray ? collections.Label.getModelsArray() : (collections.Label.models || collections.Label._models || []);
          for (const l of raw) {
            const lId = String(l.id || (l.id && l.id._serialized) || '');
            const lName = String(l.name || l.title || '');
            if (!lId && !lName) continue;

            const items = l.labelItemCollection ? (l.labelItemCollection.getModelsArray ? l.labelItemCollection.getModelsArray() : (l.labelItemCollection.models || l.labelItemCollection._models || [])) : [];
            
            // Count distinct chat JIDs (matching only Chat parentType)
            const chatJids = new Set();
            for (const item of items) {
              if (item.parentType === 'Chat' && item.parentId) {
                const jidStr = String(item.parentId);
                if (!jidStr.endsWith('@g.us')) {
                  chatJids.add(jidStr);
                }
              }
            }

            out.push({
              id: lId,
              name: lName,
              hexColor: l.hexColor || '#25D366',
              count: chatJids.size
            });
          }
        }
      } catch (e) {}
      return out;
    });

    res.json(listData);
  } catch (err) {
    console.error(`❌ Error fetching labels for [${sessionName}]:`, err);
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/labels/save-contacts', async (req, res) => {
  const { session, labelId, startOrderId, overwriteExisting } = req.body;
  const sessionName = session || 'default';
  const sessionObj = sessionsMap.get(sessionName);
  if (!sessionObj || sessionObj.status !== 'WORKING' || !sessionObj.client) {
    return res.status(503).json({ error: `Session [${sessionName}] not connected` });
  }

  let startIdNum = parseInt(startOrderId, 10);
  if (isNaN(startIdNum)) {
    return res.status(400).json({ error: 'Invalid startOrderId. Must be an integer number.' });
  }

  try {
    const saveResult = await sessionObj.client.pupPage.evaluate(async (targetLabelId, startId, overwrite) => {
      const targetStr = String(targetLabelId);
      const matchedJids = new Set();
      const collections = window.require ? window.require('WAWebCollections') : null;

      if (!collections || !collections.Label) {
        return { error: 'WAWebCollections not ready' };
      }

      // 1. Find Label and get items
      const label = collections.Label.get(targetStr) || 
                    (collections.Label.getModelsArray ? collections.Label.getModelsArray().find(l => String(l.id) === targetStr || String(l.name) === targetStr) : null);
      if (label && label.labelItemCollection) {
        const items = label.labelItemCollection.getModelsArray ? label.labelItemCollection.getModelsArray() : (label.labelItemCollection.models || []);
        for (const item of items) {
          if (item.parentType === 'Chat' && item.parentId) {
            const jid = String(item.parentId);
            if (!jid.endsWith('@g.us')) matchedJids.add(jid);
          }
        }
      }

      // 2. Gather chat metadata and resolve clean phone numbers instantly from RAM
      const chatList = [];
      for (const jid of matchedJids) {
        let cleanPhone = '';
        let pushname = '';
        let contactName = '';
        let isSaved = false;
        let timestamp = 0;

        try {
          const chat = collections.Chat ? collections.Chat.get(jid) : null;
          const contact = collections.Contact ? collections.Contact.get(jid) : null;

          if (chat) {
            timestamp = chat.t || chat.timestamp || 0;
            contactName = chat.name || chat.formattedTitle || '';
          }

          if (contact) {
            pushname = contact.pushname || '';
            contactName = contact.name || contactName;

            // Resolve real phone number instantly from in-memory contact model
            if (contact.phoneNumber && contact.phoneNumber.user) {
              cleanPhone = String(contact.phoneNumber.user);
            } else if (contact.phoneNumber && contact.phoneNumber._serialized) {
              cleanPhone = String(contact.phoneNumber._serialized).split('@')[0];
            } else if (contact.phoneNumber && typeof contact.phoneNumber === 'string') {
              cleanPhone = contact.phoneNumber.replace(/\D/g, '');
            } else if (jid.includes('@c.us')) {
              cleanPhone = jid.split('@')[0];
            }

            if (!cleanPhone) cleanPhone = String(jid).split('@')[0];

            // Contact is genuinely saved only if in phone address book or has custom contact name
            isSaved = Boolean(
              contact.isAddressBookContact || 
              contact.isMyContact || 
              (contact.name && contact.name !== cleanPhone && contact.name !== pushname && !contact.name.startsWith('+'))
            );
          } else {
            cleanPhone = String(jid).split('@')[0];
          }
        } catch (e) {
          cleanPhone = String(jid).split('@')[0];
        }

        chatList.push({
          jid: String(jid),
          phone: cleanPhone,
          name: contactName || pushname || cleanPhone,
          pushname: pushname,
          isSaved: isSaved,
          timestamp: timestamp
        });
      }

      // Sort chronologically (earliest orders first)
      chatList.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));

      // 3. Sequential numbering and saving
      let currentId = startId;
      let savedCount = 0;
      let skippedCount = 0;
      const details = [];

      const saveAction = window.require ? window.require('WAWebSaveContactAction') : null;

      for (const chat of chatList) {
        if (chat.isSaved && !overwrite) {
          skippedCount++;
          details.push({
            chatId: chat.jid,
            phone: chat.phone,
            action: 'skipped',
            name: chat.name,
            reason: 'Already saved'
          });
          continue;
        }

        const assignedName = String(currentId);
        currentId++;
        let success = false;

        // Action A: Save to WhatsApp address book with race protection
        try {
          if (saveAction && saveAction.saveContactAction && chat.phone) {
            const p = saveAction.saveContactAction({
              firstName: assignedName,
              lastName: '',
              phoneNumber: chat.phone,
              prevPhoneNumber: chat.phone,
              syncToAddressbook: false,
              username: undefined
            });
            await Promise.race([p, new Promise(r => setTimeout(r, 600))]);
            success = true;
          }
        } catch (e) {}

        // Action B: Update local contact display name model
        try {
          const c = collections.Contact ? collections.Contact.get(chat.jid) : null;
          if (c) {
            if (c.setDisplayName) await c.setDisplayName(assignedName);
            if (c.setName) await c.setName(assignedName);
            c.name = assignedName;
            c.formattedTitle = assignedName;
            success = true;
          }
        } catch (e) {}

        savedCount++;
        details.push({
          chatId: chat.jid,
          phone: chat.phone,
          assignedName: assignedName,
          action: 'saved',
          status: 'OK'
        });

        // Small 100ms pause between saves
        await new Promise(r => setTimeout(r, 100));
      }

      return {
        status: 'SUCCESS',
        totalChats: chatList.length,
        savedCount: savedCount,
        skippedCount: skippedCount,
        nextAvailableId: currentId,
        details: details
      };
    }, labelId, startIdNum, Boolean(overwriteExisting));

    if (saveResult && saveResult.error) {
      return res.status(500).json({ error: saveResult.error });
    }

    console.log(`🏷️ [${sessionName}] Order Saver completed: ${saveResult.savedCount} saved, ${saveResult.skippedCount} skipped.`);
    res.json(saveResult);

  } catch (err) {
    console.error(`❌ Error in save-contacts:`, err);
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
