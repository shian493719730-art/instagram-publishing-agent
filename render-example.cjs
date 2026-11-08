const fs = require('fs');
const path = require('path');
const { Resvg } = require('@resvg/resvg-js');

// A code-drawn test fixture, not a restaurant photo or final brand identity.
const dir = path.join(__dirname, 'media');
fs.mkdirSync(dir, { recursive: true });
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">
<rect width="1080" height="1350" fill="#F5F0E6"/>
<rect x="34" y="34" width="1012" height="1282" fill="none" stroke="#752B32" stroke-width="2"/>
<text x="540" y="145" text-anchor="middle" font-family="Arial,sans-serif" font-size="25" letter-spacing="8" fill="#752B32">YOUR BRAND</text>
<text x="540" y="420" text-anchor="middle" font-family="Georgia,serif" font-size="138" fill="#752B32">Hello,</text>
<text x="540" y="570" text-anchor="middle" font-family="Georgia,serif" font-size="116" fill="#752B32">Instagram.</text>
<g fill="none" stroke="#3B5B47" stroke-width="3">
<ellipse cx="540" cy="815" rx="175" ry="85"/><ellipse cx="540" cy="815" rx="137" ry="58"/>
<path d="M435 808C460 757 483 864 510 812S563 866 590 808S630 831 648 805"/>
<path d="M326 730V900M308 730V775Q326 797 344 775V730M326 730V775M754 730V900M740 730Q772 752 754 825"/>
</g>
<text x="540" y="1042" text-anchor="middle" font-family="Arial,sans-serif" font-size="29" fill="#3B5B47">Replace this fixture with your brand assets.</text>
<text x="540" y="1165" text-anchor="middle" font-family="Arial,sans-serif" font-size="20" letter-spacing="3" fill="#752B32">DEMONSTRATION ASSET</text>
<text x="540" y="1210" text-anchor="middle" font-family="Arial,sans-serif" font-size="18" fill="#752B32">NOT APPROVED FOR PUBLICATION</text>
</svg>`;
fs.writeFileSync(path.join(dir, 'example.svg'), svg);
const image = new Resvg(svg, { font: { loadSystemFonts: true } }).render().asPng();
fs.writeFileSync(path.join(dir, 'example.png'), image);
console.log(JSON.stringify({ output: path.join(dir, 'example.png'), width: 1080, height: 1350, bytes: image.length }));
