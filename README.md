# KPPP Platform (17 Focus Departments & K.K. Allianze Intelligence)

A modern, high-performance React application for monitoring Karnataka Public Procurement Portal (KPPP) tenders, tracking competitor commercial evaluation bids, and managing company intelligence for **K.K. Allianze** (Supplier ID: 5086).

Rewritten from the original Python backend to a responsive React SPA built with Vite and TypeScript.

---

## 🌟 Key Features

1. **Scoped 17-Department Intelligence**:
   - Strictly isolated to the 17 focus departments: `AHF`, `AHVS`, `BBMP`, `BMCRI`, `DHFWS`, `DME`, `ESISMS`, `HGML`, `INU`, `KKRDB`, `KSMSCL`, `KVAFSU`, `NIMHANS`, `RVS`, `SDSTRGI`, `SGITO`, and `SJICR`.
   - Comprehensive tracking across `GOODS`, `WORKS`, and `SERVICES` categories.
   - Interactive department pill filters showing tender volumes and status.

2. **K.K. Allianze & Proprietor Commercial Tracking**:
   - Automated detection of supplier ID `5086` and proprietor aliases (*KAMAL KUMAR PARASMAL JAIN*).
   - Commercial comparative statement analysis extracting item-by-item competitor rates, evaluated totals, rankings, and L1 winning selections.
   - Categorization into participated, won, and lost tenders with total won value metrics.
   - Competitor intelligence tracking who beat us and on how many items.
   - Item-level price comparisons comparing our bid rates and totals against winning L1 bids.

3. **Instant IND Number Search**:
   - Sub-millisecond instant matching on partial or full IND numbers (e.g., `IND2012`, `IND2505`, `IND2648`, `CALL-2`).

4. **My Tenders & Reconciliation**:
   - Direct filter for tenders automatically detected on KPPP.
   - Toggle to isolate `unknown_to_us` (new tenders discovered on the portal not in the baseline Excel sheets).

5. **Tender Details & Document Viewer**:
   - Interactive modal displaying full metadata (Department, Status, Category, Est. Value, EMD Amount, Dates).
   - Attached documents list with direct download and view access.
   - Item-by-item comparative evaluation bids and ranking tables.
   - Complete status transition timeline.

6. **Watcher Heartbeat & Simulation**:
   - Real-time portal monitoring state indicators (`WATCHING`, `SCANNING`).
   - Manual trigger option to execute an immediate reconciliation cycle and log scan runs.

---

## 🚀 Getting Started

### Development
```bash
npm install
npm run dev
```
The application will run at `http://localhost:3000`.

### Production Build
```bash
npm run build
npm run preview
```

---

## 📁 Project Structure

```
├── public/                     # Static assets and tender documents
│   └── raw/                    # Downloaded tender documents, XLSX comparative statements
├── src/
│   ├── App.tsx                 # Primary multi-tab application component
│   ├── main.tsx                # React DOM entry point
│   ├── styles.css              # Custom responsive stylesheet matching original design
│   ├── types.ts                # TypeScript interfaces for tenders, bids, departments
│   └── data/
│       └── kppp_data.json      # Complete indexed procurement dataset
├── index.html                  # HTML entry point with synchronized metadata
├── metadata.json               # Application metadata and capabilities
├── package.json                # Project dependencies and npm scripts
├── tsconfig.json               # TypeScript configuration
└── vite.config.ts              # Vite configuration (port 3000, 0.0.0.0 host)
```
