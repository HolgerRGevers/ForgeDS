'use strict';

// zoho-widget/no-unused-apis
//
// At Program:exit, appends `{ widget, file, invoked: [...] }` to the JSON
// lines file at FORGEDS_UNUSED_APIS_LOG. The Python orchestrator aggregates
// entries per widget and emits a warning diagnostic for each consumes_apis
// entry that never appeared in the invoked set across any file belonging to
// that widget.
//
// If either sidecar or log env var is missing, the rule is a silent no-op.

const fs = require('fs');
const path = require('path');

const INVOKE_METHODS = new Set([
  'invokeCustomApi',
  'invokeApi',
  'invokeConnection',
  'callFunction',
]);

function loadSidecar() {
  const p = process.env.FORGEDS_ESLINT_SIDECAR;
  if (!p) return null;
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); }
  catch (e) { return null; }
}

function resolveWidgetForFile(sidecar, filePath) {
  if (!sidecar || !sidecar.widgets) return null;
  const norm = path.resolve(filePath);
  let match = null;
  let matchLen = -1;
  for (const name of Object.keys(sidecar.widgets)) {
    const w = sidecar.widgets[name];
    const root = path.resolve(w.root || '');
    if (norm.startsWith(root + path.sep) || norm === root) {
      if (root.length > matchLen) {
        matchLen = root.length;
        match = Object.assign({ __name: name }, w);
      }
    }
  }
  return match;
}

function calleeChain(node) {
  const parts = [];
  let cur = node;
  while (cur && cur.type === 'MemberExpression') {
    if (cur.property && cur.property.type === 'Identifier') {
      parts.unshift(cur.property.name);
    } else {
      return null;
    }
    cur = cur.object;
  }
  if (cur && cur.type === 'Identifier') {
    parts.unshift(cur.name);
    return parts;
  }
  return null;
}

module.exports = {
  meta: {
    type: 'suggestion',
    docs: { description: 'Log invoked Custom APIs for post-pass unused-declaration analysis' },
    schema: [],
  },
  create(context) {
    const sidecar = loadSidecar();
    if (!sidecar) return {};
    const widget = resolveWidgetForFile(sidecar, context.getFilename());
    if (!widget) return {};
    const logPath = process.env.FORGEDS_UNUSED_APIS_LOG;
    if (!logPath) return {};

    const invoked = new Set();

    return {
      CallExpression(node) {
        const chain = calleeChain(node.callee);
        if (!chain || chain.length < 1) return;
        if (!INVOKE_METHODS.has(chain[chain.length - 1])) return;
        const first = node.arguments[0];
        if (!first || first.type !== 'Literal' || typeof first.value !== 'string') return;
        invoked.add(first.value);
      },
      'Program:exit'() {
        const entry = {
          widget: widget.__name,
          file: context.getFilename(),
          invoked: Array.from(invoked),
        };
        try {
          fs.appendFileSync(logPath, JSON.stringify(entry) + '\n', 'utf8');
        } catch (e) { /* ignore — rule is a passive observer */ }
      },
    };
  },
};
