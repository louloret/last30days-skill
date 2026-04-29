# Newsletter Signup — Next Production Step

## Goal
Let people subscribe to receive the weekly AI digest email.

## Recommended Approach: Resend Audiences

Since we're already on Resend, use their built-in Audiences feature — handles subscribers, unsubscribes, and compliance automatically.

### Steps

1. **Signup page** — static HTML hosted on GitHub Pages with a form that POSTs to Resend's Contacts API, adding the subscriber to an Audience
2. **Sending** — update `email_digest.py` to use Resend's Broadcasts API targeting the Audience, instead of the single `RESEND_TO` recipient
3. **Unsubscribes** — Resend injects the unsubscribe link automatically

### Work involved
- ~20 lines to update `email_digest.py` to use broadcasts
- A simple signup HTML page

### Tradeoff
Resend Broadcasts are a paid feature (free tier is limited). Free alternative: keep a `subscribers.txt` in a private repo and loop over recipients in `email_digest.py` — less elegant but zero cost.
