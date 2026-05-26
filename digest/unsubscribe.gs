// Web app that removes an email from subscribers.txt when called with ?email=
//
// Setup:
//   1. In Apps Script: Project Settings > Script Properties > add GITHUB_TOKEN
//      (fine-grained PAT with contents:read+write on louloret/last30days-subscribers)
//   2. Deploy > New deployment > Web app
//      - Execute as: Me
//      - Who has access: Anyone
//   3. Copy the deployment URL into ~/.config/last30days/.env as UNSUBSCRIBE_URL

const REPO = 'louloret/last30days-subscribers';
const FILE = 'subscribers.txt';
const API  = `https://api.github.com/repos/${REPO}/contents/${FILE}`;

function doGet(e) {
  const email = (e.parameter.email || '').trim().toLowerCase();

  if (!email || !email.includes('@')) {
    return HtmlService.createHtmlOutput('<p>Invalid unsubscribe link.</p>');
  }

  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  const headers = {
    'Authorization': 'Bearer ' + token,
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
  };

  // Fetch current subscribers.txt
  const getResp = UrlFetchApp.fetch(API, { headers, muteHttpExceptions: true });
  if (getResp.getResponseCode() !== 200) {
    return HtmlService.createHtmlOutput('<p>Could not process your request. Please try again later.</p>');
  }

  const data = JSON.parse(getResp.getContentText());
  const sha = data.sha;
  const current = Utilities.newBlob(
    Utilities.base64Decode(data.content.replace(/\s/g, ''))
  ).getDataAsString();

  // Remove the email (case-insensitive)
  const updated = current
    .split('\n')
    .filter(line => line.trim().toLowerCase() !== email)
    .join('\n')
    .replace(/\n{2,}/g, '\n')
    .trimEnd() + '\n';

  if (updated === current) {
    return HtmlService.createHtmlOutput(
      '<p style="font-family:sans-serif;">You\'re already unsubscribed from AI Digest.</p>'
    );
  }

  // Write back
  UrlFetchApp.fetch(API, {
    method: 'put',
    headers: { ...headers, 'Content-Type': 'application/json' },
    payload: JSON.stringify({
      message: 'unsubscribe: ' + email,
      content: Utilities.base64Encode(updated),
      sha,
    }),
    muteHttpExceptions: true,
  });

  return HtmlService.createHtmlOutput(
    '<p style="font-family:sans-serif;">You\'ve been unsubscribed from AI Digest. Sorry to see you go.</p>'
  );
}
