#!/usr/bin/env node

/* ============================================================
 * Aegis Download Manager — Electron Main Process
 * Language: Node.js (CommonJS) · Runtime: Node 22 + Electron 45
 * Platform: Windows 11 · Target: win32
 * IPC: Named Pipe \\.\pipe\Aegis_Download_Manager_Pipe
 * ============================================================
 * Clean separation: this file is the Main Process only.
 * No UI rendering here — all DOM happens in the Renderer.
 * The only job of this file: own the window, own the pipe,
 * and bridge events safely through preload.js.
 * ============================================================
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const { net } = require('net');
const path = require('path');

const PIPE_NAME = '\\\\.\\pipe\\Aegis_Download_Manager_Pipe';

class PipeRouter {
  constructor() {
    this.state = 'DISCONNECTED';
    this.pipe = null;
    this.buffer = Buffer.alloc(0);
    this.maxRetryDelay = 30000;
    this.maxRetries = 40;
    this.retryCount = 0;
    this.writeQueue = [];
    this.pendingFlushTimer = null;
    this.connectionTimer = null;
    this.eventListeners = new Map();
  }

  connect() {
    this.retryCount = 0;
    this.state = 'CONNECTING';
    this._attemptConnect();
  }

  _attemptConnect() {
    if (this.connectionTimer) { clearTimeout(this.connectionTimer); this.connectionTimer = null; }
    this.pipe = net.connect({ path: PIPE_NAME });
    this.pipe.on('connect', () => {
      this.state = 'CONNECTED';
      this.retryCount = 0;
      this.buffer = Buffer.alloc(0);
      this._debug('Pipe connected.');
      this._emit('daemon-status', { status: 'online', reason: 'connected' });
    });
    this.pipe.on('data', (chunk) => { this.buffer = Buffer.concat([this.buffer, chunk]); this._absorb(); });
    this.pipe.on('error', (err) => { this._debug('Pipe error:', err.message); });
    this.pipe.on('close', () => {
      this._debug('Pipe closed.');
      this.state = 'DISCONNECTED';
      this.pipe = null;
      this._emit('daemon-status', { status: 'offline', reason: 'connection_lost' });
      this._scheduleRetry();
    });
  }

  _absorb() {
    let idx;
    while ((idx = this.buffer.indexOf('\n'.charCodeAt(0))) !== -1) {
      const rawLine = this.buffer.slice(0, idx).toString('utf8').trim();
      this.buffer = this.buffer.slice(idx + 1);
      if (rawLine) this._dispatchMessage(rawLine);
    }
  }

  _dispatchMessage(rawJson) {
    try {
      const msg = JSON.parse(rawJson);
      const channel = msg.channel || 'unknown';
      const win = BrowserWindow.getFocusedWindow();
      if (win && win.webContents) {
        win.webContents.send('aegis-pipe-event-' + channel, { source: 'pipe', ...msg });
      }
    } catch (e) { this._debug('Malformed pipe payload ignored:', e.message); }
  }

  sendCommand(channel, payload) {
    const msg = JSON.stringify({ channel, payload }) + '\n';
    if (this.state !== 'CONNECTED') {
      this._debug('Pipe not connected; queuing command:', channel);
      this.writeQueue.push({ channel, payload, raw: msg });
      this._scheduleFlush();
      return false;
    }
    try { this.pipe.write(msg, (err) => { if (err) this._debug('Pipe write error:', err.message); }); return true; }
    catch (err) {
      this._debug('Pipe write exception:', err.message);
      this.writeQueue.push({ channel, payload, raw: msg });
      this._scheduleFlush();
      return false;
    }
  }

  _scheduleFlush() {
    if (this.pendingFlushTimer) return;
    this.pendingFlushTimer = setTimeout(() => { this.pendingFlushTimer = null; this._flushQueue(); }, 50);
  }

  _flushQueue() {
    while (this.writeQueue.length > 0 && this.state === 'CONNECTED') {
      const item = this.writeQueue.shift();
      try { this.pipe.write(item.raw, (err) => { if (err) this._debug('Flush write error:', err.message); }); }
      catch (err) { this._debug('Flush exception;', err.message); break; }
    }
  }

  _scheduleRetry() {
    if (this.retryCount >= this.maxRetries) {
      this._debug('Max retries reached. Daemon may be down.');
      this._emit('daemon-status', { status: 'unavailable', reason: 'max_retries' });
      return;
    }
    const delay = Math.min(1500 * Math.pow(2, this.retryCount), this.maxRetryDelay);
    this.retryCount++;
    this._debug('Reconnecting in ' + delay + 'ms (attempt ' + this.retryCount + ')...');
    this.connectionTimer = setTimeout(() => { this.connectionTimer = null; this._attemptConnect(); }, delay);
  }

  _startReadLoop() {}
  _debug(...args) { console.warn('[PipeRouter] ', ...args); }
}

/* ============================================================
 * MAIN APPLICATION
 * ============================================================ */

let mainWindow = null;
const pipeRouter = new PipeRouter();

function createWindow() {
  mainWindow = new BrowserWindow({
    frame: false,
    fullscreenable: true,
    center: true,
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 600,
    backgroundColor: '#0A0A0A',
    autoHideMenuBar: true,
    show: false,
    icon: path.join(__dirname, 'assets', 'icon.png'),

    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: true,
      backgroundThrottling: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));
  mainWindow.once('ready-to-show', () => { mainWindow.show(); });
  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(() => {
  createWindow();

  ipcMain.on('aegis-send-command', (event, { channel, payload }) => {
    const success = pipeRouter.sendCommand(channel, payload);
    event.sender.send('aegis-command-ack', { success, channel, ts: Date.now() });
  });

  const hasWindow = BrowserWindow.getAllWindows().length > 0;
  if (hasWindow) {
    const focused = BrowserWindow.getFocusedWindow();
    if (focused) focused.focus();
  }

  pipeRouter.connect();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'win32') app.quit();
});

app.on('will-quit', () => {
  if (pipeRouter.connectionTimer) { clearTimeout(pipeRouter.connectionTimer); pipeRouter.connectionTimer = null; }
  if (pipeRouter.pipe) { try { pipeRouter.pipe.end(); } catch (e) {} }
});

module.exports = { createWindow, pipeRouter, mainWindow };

  _emit(channel, payload) {
    const handlers = this.eventListeners.get(channel);
    if (handlers) handlers.forEach((fn) => fn(payload));
  }

  onChannel(channel, listener) {
    if (!this.eventListeners.has(channel)) this.eventListeners.set(channel, new Set());
    this.eventListeners.get(channel).add(listener);
  }

  offChannel(channel, listener) {
    const set = this.eventListeners.get(channel);
    if (set) { set.delete(listener); if (set.size === 0) this.eventListeners.delete(channel); }
  }
}