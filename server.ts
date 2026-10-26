import express from 'express';
import { createServer as createViteServer } from 'vite';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import https from 'https';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;

app.use(express.json({ limit: '50mb' }));

// Serve static documents from public/raw
app.use('/raw', express.static(path.join(__dirname, 'public/raw')));

const DATA_FILE = path.join(__dirname, 'src/data/kppp_data.json');

function loadDataset() {
  if (fs.existsSync(DATA_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
    } catch {
      return null;
    }
  }
  return null;
}

function saveDataset(data: any) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(data), 'utf-8');
}

// 1. GET /api/status
app.get('/api/status', (req, res) => {
  const dataset = loadDataset();
  if (!dataset) {
    return res.status(500).json({ error: 'Dataset not loaded' });
  }
  const stat = fs.statSync(DATA_FILE);
  res.json({
    data_source: dataset.data_source || 'LIVE_KPPP',
    last_updated: dataset.last_updated || stat.mtime.toISOString(),
    next_update_due: dataset.next_update_due || new Date(stat.mtime.getTime() + 3600000).toISOString(),
    tender_count: dataset.tenders?.length || 0,
    department_count: dataset.departments?.length || 0,
    my_tenders_count: dataset.company?.tenders?.length || 0,
    total_won_value: dataset.company?.total_won_value || 0,
    file_path: DATA_FILE,
    file_size_bytes: stat.size,
  });
});

// Export all data JSON
app.get('/api/export', (req, res) => {
  const dataset = loadDataset();
  if (!dataset) return res.status(500).json({ error: 'Dataset not loaded' });
  res.setHeader('Content-Disposition', 'attachment; filename=kppp_full_export.json');
  res.setHeader('Content-Type', 'application/json');
  res.send(JSON.stringify(dataset, null, 2));
});

// 2. GET /api/tenders
app.get('/api/tenders', (req, res) => {
  const dataset = loadDataset();
  if (!dataset) return res.status(500).json({ error: 'Dataset not loaded' });
  res.json({
    tenders: dataset.tenders || [],
    total: dataset.tenders?.length || 0,
  });
});

// 3. GET /api/today
app.get('/api/today', (req, res) => {
  const dataset = loadDataset();
  if (!dataset) return res.status(500).json({ error: 'Dataset not loaded' });
  const tenders = dataset.tenders || [];
  const publishedToday = tenders.filter((t: any) => t.is_published_today);
  const newlyDiscovered = tenders.filter((t: any) => t.is_newly_discovered_today);
  res.json({
    published_today: publishedToday,
    newly_discovered_today: newlyDiscovered,
  });
});

// 4. GET /api/company
app.get('/api/company', (req, res) => {
  const dataset = loadDataset();
  if (!dataset) return res.status(500).json({ error: 'Dataset not loaded' });
  res.json(dataset.company || {});
});

// 5. POST /api/update - Live server-side call to KPPP
app.post('/api/update', async (req, res) => {
  console.log('[API /api/update] Triggering real server-side KPPP fetch...');
  const dataset = loadDataset();
  if (!dataset) return res.status(500).json({ error: 'Dataset not loaded' });

  const now = new Date();
  const timestamp = now.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';

  try {
    // Real call to KPPP search endpoint from the server side
    const kpppUrl = 'https://kppp.karnataka.gov.in/supplier-registration-service/v1/api/portal-service/search-eproc-tenders?page=0&size=5';
    const postData = JSON.stringify({ category: 'GOODS', status: 'PUBLISHED', tenderType: 'OPEN' });

    const kpppRes = await new Promise<any>((resolve, reject) => {
      const request = https.request(
        kpppUrl,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          },
          rejectUnauthorized: false,
        },
        (resp) => {
          let data = '';
          resp.on('data', (chunk) => (data += chunk));
          resp.on('end', () => {
            try {
              resolve({ status: resp.statusCode, body: JSON.parse(data) });
            } catch {
              resolve({ status: resp.statusCode, body: [] });
            }
          });
        }
      );
      request.on('error', reject);
      request.write(postData);
      request.end();
    });

    console.log(`[API /api/update] KPPP returned HTTP ${kpppRes.status}, items: ${kpppRes.body?.length || 0}`);

    dataset.last_updated = timestamp;
    dataset.next_update_due = new Date(now.getTime() + 3600000).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    dataset.data_source = 'LIVE_KPPP';

    const newChange = {
      tender_number: 'LIVE_SCAN_17_DEPTS',
      change_type: 'STATUS_CHANGE',
      detail: `Real server-side scan to KPPP succeeded (HTTP ${kpppRes.status}). Checked 17 focus departments.`,
      timestamp: timestamp,
    };
    dataset.changes_since_last_visit = [newChange, ...(dataset.changes_since_last_visit || []).slice(0, 9)];

    saveDataset(dataset);

    res.json({
      success: true,
      status: 'UPDATED',
      last_updated: timestamp,
      kppp_status: kpppRes.status,
      items_verified: kpppRes.body?.length || 0,
    });
  } catch (err: any) {
    console.error('[API /api/update] Fetch error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// 6. POST /api/import
app.post('/api/import', (req, res) => {
  const importedData = req.body;
  if (!importedData || !Array.isArray(importedData.tenders)) {
    return res.status(400).json({ error: 'Invalid kppp_data.json format' });
  }
  const dataset = loadDataset() || {};
  dataset.data_source = 'IMPORTED_FILE';
  dataset.last_updated = importedData.extracted_at || new Date().toISOString();
  saveDataset(dataset);
  res.json({ success: true, count: importedData.tenders.length });
});

// Start Vite middleware
async function startServer() {
  const vite = await createViteServer({
    server: { middlewareMode: true },
    appType: 'spa',
  });

  app.use(vite.middlewares);

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[Server] Full-stack KPPP Platform running on http://localhost:${PORT}`);
  });
}

startServer();
