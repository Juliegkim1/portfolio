/**
 * Google Apps Script — Contact Form Handler (Resend email)
 *
 * One-time setup:
 *  1. Go to script.google.com → open (or create) this project
 *  2. Paste this code, then go to Project Settings → Script Properties
 *     Add property:  RESEND_API_KEY  →  your key from resend.com/api-keys
 *  3. In Resend, verify a sending domain (resend.com/domains).
 *     Then replace FROM_EMAIL below with an address on that domain.
 *     (e.g. "contact@yourdomain.com")
 *  4. Deploy → New deployment → Web app
 *     - Execute as: Me
 *     - Who has access: Anyone
 *  5. Copy the Web App URL → paste into gi-website/.env.local as:
 *     VITE_APPS_SCRIPT_URL=https://script.google.com/macros/s/YOUR_ID/exec
 *
 * NOTE: If you don't have a verified domain yet, Resend lets you send
 * from "onboarding@resend.dev" but ONLY to the email address registered
 * with your Resend account (good for testing).
 */

const TO_EMAIL   = 'juliegkim1@gmail.com'
const FROM_EMAIL = 'onboarding@resend.dev' // replace with your verified Resend domain address

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents)

    const apiKey = PropertiesService.getScriptProperties().getProperty('RESEND_API_KEY')
    if (!apiKey) throw new Error('RESEND_API_KEY script property is not set')

    const subject = data.subject
      ? `Portfolio Contact: ${data.subject}`
      : `Portfolio Contact from ${data.name}`

    const html = `
      <p><strong>Name:</strong> ${data.name}</p>
      <p><strong>Email:</strong> <a href="mailto:${data.email}">${data.email}</a></p>
      <p><strong>Subject:</strong> ${data.subject || '—'}</p>
      <hr>
      <p style="white-space:pre-wrap">${data.message}</p>
      <hr>
      <p style="color:#999;font-size:12px">Submitted: ${data.timestamp}</p>
    `

    const response = UrlFetchApp.fetch('https://api.resend.com/emails', {
      method: 'post',
      headers: {
        'Authorization': 'Bearer ' + apiKey,
        'Content-Type': 'application/json',
      },
      payload: JSON.stringify({
        from: 'Portfolio Contact <' + FROM_EMAIL + '>',
        to: [TO_EMAIL],
        reply_to: data.email,
        subject: subject,
        html: html,
      }),
      muteHttpExceptions: true,
    })

    const responseCode = response.getResponseCode()
    if (responseCode !== 200 && responseCode !== 201) {
      const body = JSON.parse(response.getContentText())
      throw new Error(body.message || 'Resend API error: ' + responseCode)
    }

    return ContentService
      .createTextOutput(JSON.stringify({ status: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON)

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: err.message }))
      .setMimeType(ContentService.MimeType.JSON)
  }
}

function doGet() {
  return ContentService
    .createTextOutput(JSON.stringify({ status: 'ready' }))
    .setMimeType(ContentService.MimeType.JSON)
}
