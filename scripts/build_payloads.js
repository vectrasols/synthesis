#!/usr/bin/env node
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const ROOT = path.join(__dirname, '..');
const pkg = require(path.join(ROOT, 'package.json'));
const version = pkg.version;
const platformKey = getPlatformKey();
const distDir = path.join(ROOT, 'dist');
const baselinePath = path.join(ROOT, 'main', 'payload-baseline.json');

function getPlatformKey() {
  const os = process.platform === 'win32'
    ? 'win'
    : process.platform === 'darwin'
      ? 'mac'
      : 'linux';
  return `${os}-${process.arch}`;
}

function backendPackageName() {
  return `backend-${platformKey}`;
}

function main() {
  fs.mkdirSync(distDir, { recursive: true });
  fs.mkdirSync(path.dirname(baselinePath), { recursive: true });

  const rendererFileName = `payload-renderer-${platformKey}-${version}.tgz`;
  const backendFileName = `payload-${backendPackageName()}-${version}.tgz`;

  const rendererArchive = path.join(distDir, rendererFileName);
  const backendArchive = path.join(distDir, backendFileName);

  writeArchive(rendererArchive, [
    { source: path.join(ROOT, 'renderer'), archiveRoot: 'renderer' },
    { source: path.join(ROOT, 'assets'), archiveRoot: 'assets' },
  ]);

  writeArchive(backendArchive, [
    { source: path.join(ROOT, 'python-backend', 'dist'), archiveRoot: '' },
  ]);

  const rendererPackage = packageInfo('renderer', rendererFileName, rendererArchive);
  const backendPackage = packageInfo(backendPackageName(), backendFileName, backendArchive);
  const manifest = {
    schemaVersion: 1,
    appId: pkg.build?.appId || pkg.name,
    version,
    minimumAppVersion: '1.2.0',
    platform: platformKey,
    generatedAt: new Date().toISOString(),
    packages: [rendererPackage, backendPackage],
  };

  fs.writeFileSync(
    path.join(distDir, `payload-manifest-${platformKey}.json`),
    JSON.stringify(manifest, null, 2)
  );

  fs.writeFileSync(baselinePath, JSON.stringify(manifest, null, 2));

  console.log(`[payloads] wrote ${rendererFileName}`);
  console.log(`[payloads] wrote ${backendFileName}`);
  console.log(`[payloads] wrote payload-manifest-${platformKey}.json`);
}

function packageInfo(name, fileName, filePath) {
  const data = fs.readFileSync(filePath);
  return {
    name,
    version,
    fileName,
    url: fileName,
    sha512: crypto.createHash('sha512').update(data).digest('base64'),
    size: data.length,
  };
}

function writeArchive(outputPath, roots) {
  const entries = [];
  for (const root of roots) {
    if (!fs.existsSync(root.source)) {
      throw new Error(`Payload source is missing: ${path.relative(ROOT, root.source)}`);
    }
    collectEntries(root.source, root.archiveRoot, entries);
  }

  const tar = createTar(entries.sort((a, b) => a.name.localeCompare(b.name)));
  const gz = zlib.gzipSync(tar, { level: 9, mtime: 0 });
  fs.writeFileSync(outputPath, gz);
}

function collectEntries(sourcePath, archiveRoot, entries) {
  const stat = fs.statSync(sourcePath);
  if (stat.isDirectory()) {
    for (const child of fs.readdirSync(sourcePath).sort()) {
      collectEntries(
        path.join(sourcePath, child),
        archiveRoot ? `${archiveRoot}/${child}` : child,
        entries
      );
    }
    return;
  }

  if (!stat.isFile()) return;
  entries.push({
    name: archiveRoot.replace(/\\/g, '/'),
    mode: stat.mode & 0o111 ? 0o755 : 0o644,
    data: fs.readFileSync(sourcePath),
  });
}

function createTar(entries) {
  const chunks = [];
  for (const entry of entries) {
    const header = createHeader(entry);
    chunks.push(header, entry.data);
    const padding = entry.data.length % 512;
    if (padding) chunks.push(Buffer.alloc(512 - padding));
  }
  chunks.push(Buffer.alloc(1024));
  return Buffer.concat(chunks);
}

function createHeader(entry) {
  const header = Buffer.alloc(512);
  const nameParts = splitTarName(entry.name);

  writeString(header, nameParts.name, 0, 100);
  writeOctal(header, entry.mode, 100, 8);
  writeOctal(header, 0, 108, 8);
  writeOctal(header, 0, 116, 8);
  writeOctal(header, entry.data.length, 124, 12);
  writeOctal(header, 0, 136, 12);
  header.fill(0x20, 148, 156);
  writeString(header, '0', 156, 1);
  writeString(header, 'ustar', 257, 6);
  writeString(header, '00', 263, 2);
  writeString(header, 'synthesis', 265, 32);
  writeString(header, 'synthesis', 297, 32);
  writeString(header, nameParts.prefix, 345, 155);

  let sum = 0;
  for (const byte of header) sum += byte;
  writeOctal(header, sum, 148, 8);

  return header;
}

function splitTarName(name) {
  if (Buffer.byteLength(name) <= 100) return { name, prefix: '' };

  const parts = name.split('/');
  for (let i = 1; i < parts.length; i++) {
    const prefix = parts.slice(0, i).join('/');
    const rest = parts.slice(i).join('/');
    if (Buffer.byteLength(prefix) <= 155 && Buffer.byteLength(rest) <= 100) {
      return { name: rest, prefix };
    }
  }

  throw new Error(`Payload path is too long for tar: ${name}`);
}

function writeString(buffer, value, offset, length) {
  buffer.write(String(value || '').slice(0, length), offset, length, 'utf8');
}

function writeOctal(buffer, value, offset, length) {
  const text = value.toString(8).padStart(length - 1, '0').slice(0, length - 1);
  buffer.write(text, offset, length - 1, 'ascii');
  buffer[offset + length - 1] = 0;
}

main();
