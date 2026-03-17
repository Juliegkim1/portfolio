/**
 * Google Apps Script — Contact Form Handler
 *
 * Setup steps (one-time):
 *  1. Go to script.google.com → New project → paste this code
 *  2. Replace SHEET_ID below with your Google Sheet's ID
 *     (the long string in the sheet URL between /d/ and /edit)
 *  3. Deploy → New deployment → Web app
 *     - Execute as: Me
 *     - Who has access: Anyone
 *  4. Copy the Web App URL → paste into gi-website/.env.local as:
 *     VITE_APPS_SCRIPT_URL=https://script.google.com/macros/s/YOUR_ID/exec
 */

const SHEET_ID = 'YOUR_GOOGLE_SHEET_ID_HERE'
const SHEET_NAME = 'Contacts' // name of the tab inside your sheet

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents)

    const ss = SpreadsheetApp.openById(SHEET_ID)
    let sheet = ss.getSheetByName(SHEET_NAME)

    // Auto-create the sheet and header row on first run
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME)
      sheet.appendRow(['Timestamp', 'Name', 'Email', 'Subject', 'Message'])
      sheet.getRange(1, 1, 1, 5).setFontWeight('bold')
      sheet.setFrozenRows(1)
    }

    sheet.appendRow([
      data.timestamp || new Date().toISOString(),
      data.name    || '',
      data.email   || '',
      data.subject || '',
      data.message || '',
    ])

    return ContentService
      .createTextOutput(JSON.stringify({ status: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON)

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: err.message }))
      .setMimeType(ContentService.MimeType.JSON)
  }
}

// Handles preflight OPTIONS requests (CORS)
function doGet() {
  return ContentService
    .createTextOutput(JSON.stringify({ status: 'ready' }))
    .setMimeType(ContentService.MimeType.JSON)
}
