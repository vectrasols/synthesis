#!/usr/bin/env node
'use strict';

const path = require('path');
const { runPython } = require('./run_python');

const args = [
  '-m',
  'PyInstaller',
  '--noconfirm',
  '--clean',
  '--distpath',
  path.join('python-backend', 'dist'),
  '--workpath',
  path.join('python-backend', 'build'),
  path.join('python-backend', 'server.spec'),
];

try {
  process.exitCode = runPython(args);
} catch (error) {
  console.error(`[Synthesis Suite] Backend build failed: ${error.message}`);
  process.exitCode = 1;
}
