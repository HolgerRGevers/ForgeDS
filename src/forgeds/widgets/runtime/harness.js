#!/usr/bin/env node
// ForgeDS Phase 2B — widget runtime harness.
// Requires Node >= 18. No external dependencies.
//
// Contract (spec §4):
//   argv:   --widget-root <dir> --entry-point <file>
//           --widget-name <name> --timeout-ms <ms>
//   stdout: one JSON document describing the run (success or throw or timeout).
//   stderr: FORGEDS-RUNTIME-ERROR: <json> for harness-internal errors.
//   exit:   0=ok, 4=entry_not_found, 5=throw, 6=timeout, 7=harness-internal bug.

'use strict';

const path = require('path');
const fs = require('fs');

function parseArgs(argv) {
  const out = {
    widgetRoot: null,
    entryPoint: null,
    widgetName: 'unknown',
    timeoutMs: 10000,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === '--widget-root')   { out.widgetRoot = next; i++; }
    else if (a === '--entry-point') { out.entryPoint = next; i++; }
    else if (a === '--widget-name') { out.widgetName = next; i++; }
    else if (a === '--timeout-ms')  { out.timeoutMs = parseInt(next, 10) || 10000; i++; }
  }
  return out;
}

function writeRuntimeError(reason, detail) {
  process.stderr.write(
    'FORGEDS-RUNTIME-ERROR: ' + JSON.stringify({ reason, detail }) + '\n'
  );
}

function installGlobals() {
  const sdk = require(path.join(__dirname, 'sdk_mock.js'));
  global.ZOHO = sdk.ZOHO;

  global.window = {
    addEventListener: function () {},
    removeEventListener: function () {},
    location: { href: 'about:blank' },
  };
  global.document = {
    addEventListener: function () {},
    removeEventListener: function () {},
    querySelector: function () { return null; },
    querySelectorAll: function () { return []; },
    createElement: function () {
      return {
        appendChild: function () {},
        setAttribute: function () {},
        addEventListener: function () {},
        style: {},
      };
    },
    body: { appendChild: function () {} },
    head: { appendChild: function () {} },
  };

  // Network surfaces are intentionally disabled in the harness.
  global.fetch = function () {
    throw new Error('fetch disabled in forgeds-run-widget harness');
  };
  global.XMLHttpRequest = function () {
    throw new Error('XHR disabled in forgeds-run-widget harness');
  };
  global.WebSocket = function () {
    throw new Error('WebSocket disabled in forgeds-run-widget harness');
  };
}

function main() {
  const args = parseArgs(process.argv);

  if (!args.entryPoint) {
    writeRuntimeError('entry_not_found', { reason: 'missing --entry-point argument' });
    process.exit(4);
    return;
  }
  if (!fs.existsSync(args.entryPoint)) {
    writeRuntimeError('entry_not_found', { path: args.entryPoint });
    process.exit(4);
    return;
  }

  try {
    installGlobals();
  } catch (err) {
    writeRuntimeError('harness_internal', { message: String(err && err.message) });
    process.exit(7);
    return;
  }

  const start = Date.now();
  let finished = false;

  const timer = setTimeout(function () {
    if (finished) return;
    finished = true;
    emit('timeout');
    process.exit(6);
  }, args.timeoutMs);

  function emit(status, error) {
    const payload = {
      widget: args.widgetName,
      status: status,
      durationMs: Date.now() - start,
      permissionsObserved: Array.from(
        new Set((global.ZOHO && global.ZOHO._permissionsObserved) || [])
      ),
      callLog: (global.ZOHO && global.ZOHO._callLog) || [],
    };
    if (error) {
      payload.error = {
        name: error.name,
        message: String((error && error.message) || error).slice(0, 512),
      };
    }
    process.stdout.write(JSON.stringify(payload) + '\n');
  }

  let loaded;
  try {
    loaded = require(args.entryPoint);
  } catch (err) {
    if (finished) return;
    finished = true;
    clearTimeout(timer);
    writeRuntimeError('sync_throw', { message: String(err && err.message) });
    emit('throw', err);
    process.exit(5);
    return;
  }

  Promise.resolve()
    .then(function () {
      if (loaded && typeof loaded.init === 'function') {
        return loaded.init();
      }
      return undefined;
    })
    .then(function () {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      emit('ok');
      process.exit(0);
    })
    .catch(function (err) {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      emit('throw', err);
      process.exit(5);
    });
}

main();
