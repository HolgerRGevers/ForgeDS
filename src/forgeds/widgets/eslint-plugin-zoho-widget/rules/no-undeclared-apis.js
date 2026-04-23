'use strict';

// zoho-widget/no-undeclared-apis
//
// Reports any invocation of a Custom API via ZOHO.CREATOR.API.invokeCustomApi
// (or the three aliases) whose first-string-literal argument is NOT present
// in the consumes_apis list for the widget this file belongs to.
//
// Widget context is resolved from a sidecar JSON whose path is passed via the
// FORGEDS_ESLINT_SIDECAR environment variable. If the sidecar is missing or
// does not recognise the file path, the rule is a silent no-op.

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
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch (e) {
    return null;
  }
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
    type: 'problem',
    docs: { description: 'Report Custom API invocations not listed in consumes_apis' },
    schema: [],
    messages: {
      undeclared: "widget {{widget}} invokes Custom API '{{api}}' not listed in consumes_apis",
    },
  },
  create(context) {
    const sidecar = loadSidecar();
    if (!sidecar) return {};
    const widget = resolveWidgetForFile(sidecar, context.getFilename());
    if (!widget) return {};
    const declared = new Set(widget.consumesApis || widget.consumes_apis || []);

    return {
      CallExpression(node) {
        const chain = calleeChain(node.callee);
        if (!chain || chain.length < 1) return;
        const last = chain[chain.length - 1];
        if (!INVOKE_METHODS.has(last)) return;
        const first = node.arguments[0];
        if (!first || first.type !== 'Literal' || typeof first.value !== 'string') return;
        const apiName = first.value;
        if (!declared.has(apiName)) {
          context.report({
            node,
            messageId: 'undeclared',
            data: { widget: widget.__name, api: apiName },
          });
        }
      },
    };
  },
};
