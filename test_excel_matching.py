import json
import re

with open('data/existing_excel_inds.json') as f:
    excel_inds = json.load(f)

with open('src/data/kppp_data.json') as f:
    data = json.load(f)

def normalize_key(tender_str):
    if not tender_str:
        return ""
    # Strip whitespace and uppercase
    s = str(tender_str).strip().upper()
    # Remove financial year pattern like /2023-24/, /2024-25/, /2025-26/, /2026-27/
    s_no_yr = re.sub(r'/\d{4}-\d{2}/', '/', s)
    # Also extract just the IND number like IND2454 or IND2454/CALL-2
    ind_match = re.search(r'(IND\d+(?:/CALL-\d+)?)', s)
    ind_num = ind_match.group(1) if ind_match else ""
    return s, s_no_yr, ind_num

excel_norm_full = set()
excel_norm_noyr = set()
excel_norm_ind = set()

for e in excel_inds:
    f, ny, ind = normalize_key(e)
    excel_norm_full.add(f)
    excel_norm_noyr.add(ny)
    if ind:
        excel_norm_ind.add(ind)

print('Loaded Excel entries:', len(excel_inds))
print('Sample Excel entries:', excel_inds[:5])

# Test on K.K. Allianze participated tenders
kk_tenders = data['company']['tenders']
print(f'\nTotal K.K. Allianze Participated Tenders: {len(kk_tenders)}')

matched_samples = []
unmatched_samples = []

for t in kk_tenders:
    t_num = t['tender_number']
    f, ny, ind = normalize_key(t_num)
    
    # Check matching
    is_match = (f in excel_norm_full) or (ny in excel_norm_noyr) or (ind in excel_norm_ind)
    
    if is_match:
        matched_samples.append((t_num, ny, ind))
    else:
        unmatched_samples.append((t_num, ny, ind))

print(f'\nTOTAL MATCHED IN EXCEL:   {len(matched_samples)}')
print(f'TOTAL UNMATCHED (NEW ON PORTAL): {len(unmatched_samples)}')

print('\n========================================================================================')
print('PROOF 4: NORMALIZED MATCHING AUDIT — 10 MATCHED AND 10 UNMATCHED SIDE-BY-SIDE')
print('========================================================================================')
print(f'{"#":<3} | {"MATCHED (IN EXCEL BASELINE)":<40} | {"UNMATCHED (NEWLY DISCOVERED ON KPPP)":<40}')
print('-'*90)

for i in range(10):
    m_text = matched_samples[i][0] if i < len(matched_samples) else "—"
    u_text = unmatched_samples[i][0] if i < len(unmatched_samples) else "—"
    print(f'{i+1:<3} | {m_text:<40} | {u_text:<40}')

print('========================================================================================')
