#!/usr/bin/env node
'use strict';

const { execFileSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');

function pythonPathsFromEnvRoot(envRoot) {
  if (!envRoot) return null;
  return process.platform === 'win32'
    ? [path.join(envRoot, 'Scripts', 'python.exe'), path.join(envRoot, 'python.exe')]
    : [path.join(envRoot, 'bin', 'python')];
}

function commandWorks(command, args = ['--version']) {
  try {
    execFileSync(command, args, { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

function fileWorks(filePath) {
  return Boolean(filePath && fs.existsSync(filePath) && commandWorks(filePath));
}

function findCondaEnvCommand(envName) {
  if (!envName || !commandWorks('conda')) return null;

  try {
    execFileSync('conda', ['run', '-n', envName, 'python', '--version'], { stdio: 'ignore' });
    return { command: 'conda', prefixArgs: ['run', '-n', envName, 'python'] };
  } catch {
    return null;
  }
}

function resolvePython() {
  const explicitPython = process.env.SYNTHESIS_PYTHON;
  if (explicitPython) {
    if (fs.existsSync(explicitPython) || commandWorks(explicitPython)) {
      return { command: explicitPython, prefixArgs: [] };
    }
    throw new Error(`SYNTHESIS_PYTHON does not point to a runnable Python: ${explicitPython}`);
  }

  const envRoots = [
    process.env.SYNTHESIS_VENV,
    path.join(rootDir, '.venv'),
    process.env.VIRTUAL_ENV,
    process.env.CONDA_PREFIX,
  ];

  for (const envRoot of envRoots) {
    for (const pythonPath of pythonPathsFromEnvRoot(envRoot) || []) {
      if (fileWorks(pythonPath)) {
        return { command: pythonPath, prefixArgs: [] };
      }
    }
  }

  const condaCommand = findCondaEnvCommand(process.env.SYNTHESIS_CONDA_ENV);
  if (condaCommand) return condaCommand;

  const candidates = process.platform === 'win32' ? ['python'] : ['python3', 'python'];
  for (const candidate of candidates) {
    if (commandWorks(candidate)) {
      return { command: candidate, prefixArgs: [] };
    }
  }

  throw new Error(
    'Python 3 was not found. Create .venv, activate a virtual environment, ' +
    'or set SYNTHESIS_PYTHON to a Python executable.'
  );
}

function runPython(args, options = {}) {
  const resolved = resolvePython();
  const result = spawnSync(resolved.command, [...resolved.prefixArgs, ...args], {
    stdio: 'inherit',
    cwd: rootDir,
    env: process.env,
    ...options,
  });

  if (result.error) throw result.error;
  return result.status ?? 1;
}

if (require.main === module) {
  try {
    process.exitCode = runPython(process.argv.slice(2));
  } catch (error) {
    console.error(`[Synthesis Suite] ${error.message}`);
    process.exitCode = 1;
  }
}

module.exports = { resolvePython, runPython };
