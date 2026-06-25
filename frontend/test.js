const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();

  page.on('console', msg => {
    console.log(`[CONSOLE] ${msg.type().toUpperCase()} ${msg.text()}`);
  });
  
  page.on('pageerror', error => {
    console.log(`[PAGE ERROR] ${error.message}`);
  });
  
  page.on('response', response => {
    if (response.status() >= 400) {
      console.log(`[HTTP ERROR] ${response.status()} ${response.url()}`);
    }
  });
  
  page.on('requestfailed', request => {
    console.log(`[REQUEST FAILED] ${request.failure().errorText} ${request.url()}`);
  });

  await page.goto('http://localhost:8080/index.html', {waitUntil: 'networkidle0'});
  await new Promise(r => setTimeout(r, 5000));
  await browser.close();
})();
