// Triggered on Google Form submit. Appends the submitted email to
// subscribers.txt in the private louloret/last30days-subscribers repo.
//
// Setup:
//   1. In Apps Script: Project Settings > Script Properties > add GITHUB_TOKEN
//      (fine-grained PAT with contents:read+write on louloret/last30days-subscribers)
//   2. In Apps Script: Triggers > Add trigger > onFormSubmit > From form > On form submit

const REPO = 'louloret/last30days-subscribers';
const FILE = 'subscribers.txt';
const API  = `https://api.github.com/repos/${REPO}/contents/${FILE}`;

function onFormSubmit(e) {
  // e.values[0] = timestamp, e.values[1] = email field
  const email = (e.values[1] || '').trim().toLowerCase();
  if (!email || !email.includes('@')) return;

  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  const headers = {
    'Authorization': 'Bearer ' + token,
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
  };

  // Fetch current file (may not exist yet)
  let sha = null;
  let current = '';
  const getResp = UrlFetchApp.fetch(API, { headers, muteHttpExceptions: true });
  if (getResp.getResponseCode() === 200) {
    const data = JSON.parse(getResp.getContentText());
    sha = data.sha;
    current = Utilities.newBlob(
      Utilities.base64Decode(data.content.replace(/\s/g, ''))
    ).getDataAsString();
  }

  // Skip duplicates
  const existing = current.split('\n').map(s => s.trim().toLowerCase()).filter(Boolean);
  if (existing.includes(email)) return;

  // Append and write back
  const updated = (current.trimEnd() + (current.trim() ? '\n' : '') + email + '\n');
  const body = { message: 'subscriber: ' + email, content: Utilities.base64Encode(updated) };
  if (sha) body.sha = sha;

  UrlFetchApp.fetch(API, {
    method: 'put',
    headers: { ...headers, 'Content-Type': 'application/json' },
    payload: JSON.stringify(body),
    muteHttpExceptions: true,
  });
}
