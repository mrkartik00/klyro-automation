const express = require('express');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;
const BASE_DIR = __dirname;
const LOG_FILE = path.join(BASE_DIR, 'sent_emails_log.txt');

app.use(express.json());
app.use(express.static(path.join(BASE_DIR, 'public')));

// ─── State ────────────────────────────────────────────────────────────────────
let emailProcess = null;
let isRunning = false;
let liveLogBuffer = []; // in-memory recent lines for dashboard
let stats = { success: 0, failed: 0, skipped: 0, total: 0 };

function addLog(line) {
  const trimmed = line.trim();
  if (!trimmed) return;
  liveLogBuffer.push({ ts: new Date().toISOString(), msg: trimmed });
  if (liveLogBuffer.length > 1000) liveLogBuffer.shift(); // cap at 1000 lines

  // parse stats from the Python script's stdout
  if (trimmed.startsWith('Skipping')) stats.skipped++;
  const m = trimmed.match(/\((\d+) sent, (\d+) failed\)/);
  if (m) { stats.success = parseInt(m[1]); stats.failed = parseInt(m[2]); }
}

// ─── API: Status ──────────────────────────────────────────────────────────────
app.get('/api/status', (req, res) => {
  res.json({ isRunning, stats });
});

// ─── API: Logs ────────────────────────────────────────────────────────────────
app.get('/api/logs', (req, res) => {
  // Return live buffer + a slice of the persistent log file
  let fileLogs = [];
  if (fs.existsSync(LOG_FILE)) {
    const content = fs.readFileSync(LOG_FILE, 'utf8');
    fileLogs = content
      .split('\n')
      .filter(Boolean)
      .map(line => ({ ts: null, msg: line, persisted: true }));
  }
  res.json({ live: liveLogBuffer, file: fileLogs.slice(-500) });
});

// ─── API: Start ───────────────────────────────────────────────────────────────
app.post('/api/start', (req, res) => {
  if (isRunning) return res.status(400).json({ error: 'Already running.' });

  const subject = req.body.subject || 'Enhancing Your Digital Presence';
  const args = [path.join(BASE_DIR, 'send_emails.py'), '--subject', subject];

  liveLogBuffer = [];
  stats = { success: 0, failed: 0, skipped: 0, total: 0 };

  emailProcess = spawn('python3', args, {
    cwd: BASE_DIR,
    env: { ...process.env },
  });

  isRunning = true;
  addLog(`▶ Started email campaign | Subject: "${subject}"`);

  emailProcess.stdout.on('data', (data) => {
    const lines = data.toString().split('\n');
    lines.forEach(addLog);
  });

  emailProcess.stderr.on('data', (data) => {
    const lines = data.toString().split('\n');
    lines.forEach(line => addLog(`[ERR] ${line}`));
  });

  emailProcess.on('close', (code) => {
    isRunning = false;
    emailProcess = null;
    addLog(`■ Process exited with code ${code}. Stats → ✓ ${stats.success} sent, ✗ ${stats.failed} failed, ⏭ ${stats.skipped} skipped.`);
  });

  res.json({ ok: true, message: 'Email sending started.' });
});

// ─── API: Stop ────────────────────────────────────────────────────────────────
app.post('/api/stop', (req, res) => {
  if (!isRunning || !emailProcess) {
    return res.status(400).json({ error: 'No running process.' });
  }
  emailProcess.kill('SIGTERM');
  isRunning = false;
  addLog('■ Email sending manually stopped.');
  res.json({ ok: true, message: 'Stopped.' });
});

// ─── API: Test Send ───────────────────────────────────────────────────────────
app.post('/api/test', (req, res) => {
  if (isRunning) return res.status(400).json({ error: 'A job is already running.' });

  const subject = req.body.subject || 'Enhancing Your Digital Presence';
  const args = [path.join(BASE_DIR, 'send_emails.py'), '--test', '--subject', subject];

  liveLogBuffer = [];
  emailProcess = spawn('python3', args, { cwd: BASE_DIR, env: { ...process.env } });
  isRunning = true;
  addLog(`🧪 Running TEST send | Subject: "${subject}"`);

  emailProcess.stdout.on('data', (data) => data.toString().split('\n').forEach(addLog));
  emailProcess.stderr.on('data', (data) => data.toString().split('\n').forEach(l => addLog(`[ERR] ${l}`)));
  emailProcess.on('close', (code) => {
    isRunning = false;
    emailProcess = null;
    addLog(`■ Test finished (code ${code}).`);
  });

  res.json({ ok: true });
});

// ─── Serve dashboard ──────────────────────────────────────────────────────────
app.get('/', (req, res) => {
  res.sendFile(path.join(BASE_DIR, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Klyro Email Server running on port ${PORT}`);
});
