# Newsletter Google Form + Apps Script Setup

## Step 1: Create the Google Form
1. Go to **forms.google.com** → Blank form
2. Title it: `Subscribe to AI Digest`
3. Change the default question to type **Short answer**, label it `Email address`, mark it **Required**
4. Click the settings gear → **Presentation** → set confirmation message: `You're subscribed! First digest arrives Monday.`
5. Hit **Send** → copy the form link (drop this in the README later)

## Step 2: Open the linked spreadsheet
1. In the form editor, click the **Responses** tab
2. Click the green **Google Sheets** icon → Create new spreadsheet → **Create**

## Step 3: Open Apps Script
1. In the spreadsheet, click **Extensions → Apps Script**
2. Delete everything in the default `Code.gs` file
3. Paste the contents of `digest/subscribe.gs` from the repo

## Step 4: Add the GitHub token
1. In Apps Script, click the gear icon → **Project Settings**
2. Scroll to **Script Properties** → **Add script property**
   - Property: `GITHUB_TOKEN`
   - Value: your fine-grained PAT (same one added as `GH_SUBSCRIBERS_TOKEN` in Actions)
3. Click **Save script properties**

## Step 5: Set the trigger
1. In Apps Script, click the clock icon (**Triggers**) in the left sidebar
2. Click **+ Add Trigger** (bottom right)
3. Settings:
   - Function: `onFormSubmit`
   - Event source: **From form**
   - Event type: **On form submit**
4. Click **Save** → authorize when prompted

## Step 6: Test it
1. Go back to the form → click the eye icon (preview) → submit a test email
2. Check `louloret/last30days-subscribers` → `subscribers.txt` should have the new entry within a few seconds

---

Once working, drop the form URL in the README as the signup CTA.
