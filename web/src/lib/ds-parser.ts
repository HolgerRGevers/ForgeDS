/**
 * DSParser - TypeScript port of forgeds/core/parse_ds_export.py
 *
 * Parses forms, fields, workflows, schedules, and approvals.
 */

export interface FormField {
  linkName: string;
  displayName: string;
  fieldType: string;
  notes: string;
}

export interface FormDef {
  name: string;
  displayName: string;
  fields: FormField[];
}

export interface ScriptDef {
  name: string;
  displayName: string;
  form: string;
  event: string;
  trigger: string;
  code: string;
  context: string;
}

const SKIP_FIELDS = new Set([
  'Section', 'actions', 'submit', 'reset', 'update', 'cancel',
]);

export class DSParser {
  private lines: string[];
  public forms: FormDef[] = [];
  public scripts: ScriptDef[] = [];

  constructor(content: string) {
    this.lines = content.split(/\r?\n/);
  }

  parse(): void {
    this.parseForms();
    this.parseWorkflows();
    this.parseSchedules();
    this.parseApprovals();
  }

  // ----------------------------------------------------------
  // Task 1: Form and field parsing
  // ----------------------------------------------------------

  private parseForms(): void {
    for (let i = 0; i < this.lines.length; i++) {
      const m = /^\t{2,3}form\s+(\w+)\s*$/.exec(this.lines[i]);
      if (m && i + 1 < this.lines.length && this.lines[i + 1].trim() === '{') {
        const formName = m[1];
        const form = this.parseSingleForm(formName, i);
        if (form && form.fields.length > 0) {
          this.forms.push(form);
        }
      }
    }
  }

  private parseSingleForm(formName: string, start: number): FormDef | null {
    let displayName = formName;
    const fields: FormField[] = [];
    let braceDepth = 0;
    let inForm = false;
    let gotDisplayName = false;
    let i = start;

    while (i < this.lines.length) {
      const line = this.lines[i];
      const stripped = line.trim();

      if (stripped.includes('{')) {
        braceDepth += this.countChar(stripped, '{');
        if (!inForm) inForm = true;
      }
      if (stripped.includes('}')) {
        braceDepth -= this.countChar(stripped, '}');
        if (inForm && braceDepth <= 0) break;
      }

      if (braceDepth === 1 && !gotDisplayName) {
        const dm = /^\s*displayname\s*=\s*"([^"]*)"/. exec(stripped);
        if (dm) { displayName = dm[1]; gotDisplayName = true; }
      }

      if (braceDepth === 1 && i + 1 < this.lines.length) {
        const fm = /^\s*(?:must have\s+)?(\w+)\s*$/.exec(stripped);
        if (fm && this.lines[i + 1].trim() === '(') {
          const fieldLink = fm[1];
          if (!SKIP_FIELDS.has(fieldLink)) {
            const f = this.parseField(fieldLink, i + 1);
            if (f) fields.push(f);
          }
        }
      }

      i++;
    }

    return fields.length === 0 ? null : { name: formName, displayName, fields };
  }

  private parseField(linkName: string, parenStart: number): FormField | null {
    let fieldType = '';
    let displayName = linkName;
    const notesParts: string[] = [];
    let parenDepth = 0;
    let i = parenStart;

    while (i < this.lines.length) {
      const stripped = this.lines[i].trim();
      parenDepth += this.countChar(stripped, '(') - this.countChar(stripped, ')');

      const tm = /^type\s*=\s*(\w[\w\s]*)/.exec(stripped);
      if (tm) fieldType = tm[1].trim();

      const dnm = /^displayname\s*=\s*"([^"]*)"/. exec(stripped);
      if (dnm) displayName = dnm[1];

      if (stripped.includes('personal data = true')) notesParts.push('personal data');
      if (stripped.includes('private = true')) notesParts.push('private/hidden');
      const ivm = /initial value\s*=\s*(\S+)/.exec(stripped);
      if (ivm) notesParts.push('default: ' + ivm[1]);

      if (parenDepth <= 0 && i > parenStart) break;
      i++;
    }

    if (!fieldType) return null;
    return { linkName, displayName, fieldType, notes: notesParts.join(', ') };
  }

  // ----------------------------------------------------------
  // Task 2: Workflow, schedule, approval, script extraction
  // ----------------------------------------------------------

  private extractScriptCode(parenLine: number): string {
    const codeLines: string[] = [];
    let parenDepth = 0;
    let started = false;
    let i = parenLine;

    while (i < this.lines.length) {
      const line = this.lines[i];
      const stripped = line.trim();

      parenDepth += this.countChar(stripped, '(') - this.countChar(stripped, ')');

      if (!started && stripped.includes('(')) {
        started = true;
        const parenIdx = stripped.indexOf('(');
        const afterParen = stripped.substring(parenIdx + 1).trim();
        if (afterParen) codeLines.push(afterParen);
        i++;
        continue;
      }

      if (started) {
        if (parenDepth <= 0) {
          const lastClose = stripped.lastIndexOf(')');
          const beforeParen = lastClose >= 0
            ? stripped.substring(0, lastClose).trim()
            : stripped.trim();
          if (beforeParen) codeLines.push(beforeParen);
          break;
        }
        codeLines.push(line.trimEnd());
      }

      i++;
    }

    if (codeLines.length === 0) return '';
    const nonEmpty = codeLines.filter(l => l.trim().length > 0);
    if (nonEmpty.length === 0) return '';

    const minIndent = Math.min(...nonEmpty.map(l => l.length - l.trimStart().length));
    const dedented = codeLines.map(l =>
      l.length > minIndent ? l.substring(minIndent) : l.trimStart()
    );
    return dedented.join('\n').trim();
  }
  private parseWorkflows(): void {
    for (let i = 0; i < this.lines.length; i++) {
      const stripped = this.lines[i].trim();
      const wm = /^\s*(\w+)\s+as\s+"([^"]*)"/.exec(stripped);
      if (!wm) continue;

      const name = wm[1];
      const display = wm[2];
      let formName = '';
      let recordEvent = '';
      let eventType = '';
      let code = '';
      let j = i + 1;
      let braceDepth = 0;
      let inBlock = false;

      while (j < this.lines.length) {
        const line = this.lines[j].trim();

        if (line.includes('{')) {
          braceDepth += this.countChar(line, '{');
          inBlock = true;
        }
        if (line.includes('}')) {
          braceDepth -= this.countChar(line, '}');
          if (inBlock && braceDepth <= 0) break;
        }

        const fm = /^form\s*=\s*(\w+)/.exec(line);
        if (fm) formName = fm[1];

        const rem = /^record event\s*=\s*(.+)/.exec(line);
        if (rem) recordEvent = rem[1].trim();

        for (const evt of ['on success', 'on validate', 'on load', 'on update of']) {
          if (line.startsWith(evt)) eventType = evt;
        }

        if (line === 'custom deluge script') {
          code = this.extractScriptCode(j + 1);
        }

        j++;
      }

      if (code && formName) {
        this.scripts.push({
          name,
          displayName: display,
          form: formName,
          event: eventType || 'on success',
          trigger: recordEvent || 'on add',
          code,
          context: 'form-workflow',
        });
      }
    }
  }

  private parseSchedules(): void {
    for (let i = 0; i < this.lines.length; i++) {
      const stripped = this.lines[i].trim();
      if (stripped.startsWith('schedule') && i + 1 < this.lines.length) {
        if (this.lines[i + 1].trim() === '{') {
          this.parseScheduleBlock(i + 2);
        }
      }
    }
  }

  private parseScheduleBlock(start: number): void {
    let i = start;
    while (i < this.lines.length) {
      const stripped = this.lines[i].trim();
      const sm = /^(\w+)\s+as\s+"([^"]*)"/.exec(stripped);
      if (sm) {
        const name = sm[1];
        const display = sm[2];
        let formName = '';
        let code = '';
        let j = i + 1;
        let braceDepth = 0;

        while (j < this.lines.length) {
          const line = this.lines[j].trim();
          braceDepth += this.countChar(line, '{') - this.countChar(line, '}');

          const fm = /^form\s*=\s*(\w+)/.exec(line);
          if (fm) formName = fm[1];

          if (line === 'on load') {
            if (j + 1 < this.lines.length && this.lines[j + 1].includes('(')) {
              code = this.extractScriptCode(j + 1);
            }
          }

          if (braceDepth < 0) break;
          j++;
        }

        if (code) {
          this.scripts.push({
            name,
            displayName: display,
            form: formName,
            event: 'on load',
            trigger: 'scheduled',
            code,
            context: 'scheduled',
          });
        }
      }
      i++;
    }
  }

  private parseApprovals(): void {
    for (let i = 0; i < this.lines.length; i++) {
      const stripped = this.lines[i].trim();
      if (stripped.startsWith('approval') && i + 1 < this.lines.length) {
        if (this.lines[i + 1].trim() === '{') {
          this.parseApprovalBlock(i + 2);
          break;
        }
      }
    }
  }

  private parseApprovalBlock(start: number): void {
    let i = start;
    let currentApproval = '';
    let currentDisplay = '';

    while (i < this.lines.length) {
      const stripped = this.lines[i].trim();

      const am = /^(\w+)\s+as\s+"([^"]*)"/.exec(stripped);
      if (am) {
        currentApproval = am[1];
        currentDisplay = am[2];
      }

      for (const event of ['on approve', 'on reject']) {
        if (stripped.startsWith(event)) {
          let j = i + 1;
          while (j < this.lines.length) {
            const lineJ = this.lines[j].trim();
            if (lineJ === 'on load') {
              if (j + 1 < this.lines.length && this.lines[j + 1].includes('(')) {
                const code = this.extractScriptCode(j + 1);
                if (code) {
                  this.scripts.push({
                    name: currentApproval + '_' + event.replace(' ', '_'),
                    displayName: currentDisplay + ' - ' + this.titleCase(event),
                    form: 'expense_claims',
                    event,
                    trigger: 'approval',
                    code,
                    context: 'approval',
                  });
                }
              }
              break;
            }
            if (lineJ.includes('}') && !lineJ.includes('{')) break;
            j++;
          }
        }
      }

      i++;
    }
  }

  // ----------------------------------------------------------
  // Helpers
  // ----------------------------------------------------------

  private countChar(str: string, ch: string): number {
    let count = 0;
    for (const c of str) { if (c === ch) count++; }
    return count;
  }

  private titleCase(str: string): string {
    return str.replace(/\b\w/g, c => c.toUpperCase());
  }
}

