/**
 * DSParser - TypeScript port of forgeds/core/parse_ds_export.py
 *
 * Task 1: Data structures and form/field parsing.
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
      const m = /^	{2,3}forms+(w+)s*$/.exec(this.lines[i]);
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
        const dm = /^s*displaynames*=s*"([^"]*)"/. exec(stripped);
        if (dm) { displayName = dm[1]; gotDisplayName = true; }
      }

      if (braceDepth === 1 && i + 1 < this.lines.length) {
        const fm = /^s*(?:must haves+)?(w+)s*$/.exec(stripped);
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

      const tm = /^types*=s*(w[ws]*)/.exec(stripped);
      if (tm) fieldType = tm[1].trim();

      const dnm = /^displaynames*=s*"([^"]*)"/. exec(stripped);
      if (dnm) displayName = dnm[1];

      if (stripped.includes('personal data = true')) notesParts.push('personal data');
      if (stripped.includes('private = true')) notesParts.push('private/hidden');
      const ivm = /initial values*=s*(S+)/.exec(stripped);
      if (ivm) notesParts.push('default: ' + ivm[1]);

      if (parenDepth <= 0 && i > parenStart) break;
      i++;
    }

    if (!fieldType) return null;
    return { linkName, displayName, fieldType, notes: notesParts.join(', ') };
  }

  // ----------------------------------------------------------
  // Helpers
  // ----------------------------------------------------------

  protected countChar(str: string, ch: string): number {
    let count = 0;
    for (const c of str) { if (c === ch) count++; }
    return count;
  }

  protected titleCase(str: string): string {
    return str.replace(/w/g, c => c.toUpperCase());
  }

  // Workflow/schedule/approval parsing — added in Task 2
  protected parseWorkflows(): void {}
  protected parseSchedules(): void {}
  protected parseApprovals(): void {}
}
