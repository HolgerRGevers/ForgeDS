/**
 * Monaco Editor language definition for Zoho Deluge.
 *
 * Registers a "deluge" language (Monarch tokenizer) and a companion
 * dark theme ("deluge-dark") that matches the app's gray-900/950 palette.
 */

const THEME_NAME = "deluge-dark";

export { THEME_NAME as DELUGE_THEME };

export function registerDelugeLanguage(
  monaco: typeof import("monaco-editor"),
): void {
  // Guard against double-registration
  if (
    monaco.languages.getLanguages().some((lang) => lang.id === "deluge")
  ) {
    return;
  }

  // --- Language registration -------------------------------------------

  monaco.languages.register({
    id: "deluge",
    extensions: [".dg"],
    aliases: ["Deluge", "deluge"],
  });

  // --- Monarch tokenizer ----------------------------------------------

  monaco.languages.setMonarchTokensProvider("deluge", {
    defaultToken: "",
    ignoreCase: false,

    keywords: [
      "if",
      "else",
      "for",
      "each",
      "in",
      "return",
      "true",
      "false",
      "null",
      "and",
      "or",
      "not",
      "void",
      "break",
      "continue",
    ],

    controlFlow: ["cancel", "submit"],

    builtinTasks: ["sendmail", "alert", "info", "openUrl", "invokeUrl"],

    dataTypes: [
      "text",
      "number",
      "decimal",
      "boolean",
      "date",
      "datetime",
      "list",
      "map",
    ],

    builtinFunctions: [
      "ifnull",
      "contains",
      "size",
      "count",
      "add",
      "put",
      "get",
      "remove",
      "trim",
      "toUpperCase",
      "toLowerCase",
      "toString",
      "toNumber",
      "toDate",
      "toTime",
      "getPrefix",
      "getSuffix",
      "replaceAll",
      "startsWith",
      "endsWith",
      "length",
      "daysBetween",
      "now",
      "substring",
      "indexOf",
    ],

    operators: [
      "==",
      "!=",
      ">=",
      "<=",
      ">",
      "<",
      "&&",
      "||",
      "+",
      "-",
      "*",
      "/",
      "=",
    ],

    symbols: /[=><!~?:&|+\-*/^%]+/,

    tokenizer: {
      root: [
        // Whitespace
        [/\s+/, "white"],

        // Comments
        [/\/\/.*$/, "comment"],
        [/\/\*/, "comment", "@comment"],

        // "insert into" keyword pair
        [/\b(insert)\s+(into)\b/, { token: "keyword" }],

        // Zoho system variables: zoho.xxx
        [
          /\bzoho\.(loginuser|loginuserid|adminuserid|currentdate|currenttime|appname)\b/,
          "zoho-variable",
        ],

        // thisapp.permissions.isUserInRole
        [/\bthisapp\.permissions\.isUserInRole\b/, "zoho-variable"],

        // input.FieldName
        [/\binput\.[A-Za-z_]\w*/, "zoho-variable"],

        // Date literals — single-quoted strings like '2026-04-06'
        [/'[^']*'/, "date-literal"],

        // Double-quoted strings
        [/"/, "string", "@string"],

        // Numbers (decimal and integer)
        [/\b\d+\.\d+\b/, "number.float"],
        [/\b\d+\b/, "number"],

        // Identifiers and keywords
        [
          /[a-zA-Z_]\w*/,
          {
            cases: {
              "@keywords": "keyword",
              "@controlFlow": "keyword.control",
              "@builtinTasks": "builtin-task",
              "@dataTypes": "type",
              "@builtinFunctions": "builtin-function",
              "@default": "identifier",
            },
          },
        ],

        // Bracket syntax blocks (square brackets for tasks)
        [/[[\]]/, "delimiter.square"],
        [/[{}]/, "delimiter.curly"],
        [/[()]/, "delimiter.parenthesis"],

        // Operators
        [
          /@symbols/,
          {
            cases: {
              "@operators": "operator",
              "@default": "",
            },
          },
        ],

        // Semicolons and other punctuation
        [/[;,.]/, "delimiter"],
      ],

      comment: [
        [/[^/*]+/, "comment"],
        [/\*\//, "comment", "@pop"],
        [/[/*]/, "comment"],
      ],

      string: [
        [/[^"\\]+/, "string"],
        [/\\./, "string.escape"],
        [/"/, "string", "@pop"],
      ],
    },
  });

  // --- Theme -----------------------------------------------------------

  monaco.editor.defineTheme(THEME_NAME, {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "keyword", foreground: "569CD6", fontStyle: "bold" },
      { token: "keyword.control", foreground: "569CD6", fontStyle: "bold" },
      { token: "string", foreground: "CE9178" },
      { token: "string.escape", foreground: "D7BA7D" },
      { token: "date-literal", foreground: "B5CEA8" },
      { token: "number", foreground: "B5CEA8" },
      { token: "number.float", foreground: "B5CEA8" },
      { token: "comment", foreground: "6A9955", fontStyle: "italic" },
      { token: "zoho-variable", foreground: "C586C0" },
      { token: "builtin-function", foreground: "DCDCAA" },
      { token: "builtin-task", foreground: "D7BA7D", fontStyle: "bold" },
      { token: "operator", foreground: "D4D4D4" },
      { token: "type", foreground: "4EC9B0" },
      { token: "delimiter", foreground: "D4D4D4" },
      { token: "delimiter.square", foreground: "D7BA7D" },
      { token: "identifier", foreground: "9CDCFE" },
    ],
    colors: {
      "editor.background": "#0a0a0f",
      "editor.foreground": "#D4D4D4",
    },
  });
}
