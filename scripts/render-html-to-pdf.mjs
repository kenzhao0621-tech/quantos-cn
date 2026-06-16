#!/usr/bin/env node
/** Render HTML to PDF via Playwright — deterministic printToPDF */
import { chromium } from '@playwright/test';
import { fileURLToPath } from 'url';
import path from 'path';

const [,, htmlPath, pdfPath] = process.argv;
if (!htmlPath || !pdfPath) {
  console.error('Usage: node render-html-to-pdf.mjs <html> <pdf>');
  process.exit(1);
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto('file://' + path.resolve(htmlPath), { waitUntil: 'networkidle' });
await page.pdf({
  path: pdfPath,
  format: 'A4',
  printBackground: true,
  margin: { top: '20mm', bottom: '20mm', left: '15mm', right: '15mm' },
});
await browser.close();
console.log('PDF written:', pdfPath);
