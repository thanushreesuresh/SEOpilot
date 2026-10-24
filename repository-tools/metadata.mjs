import ts from "typescript";
import { pathToFileURL } from "node:url";

const MAX_INPUT_BYTES = 2 * 1024 * 1024;
const MAX_FILES = 500;
const MAX_FILE_BYTES = 128 * 1024;

export class UnsupportedMetadata extends Error {}

function fail(message) {
  throw new UnsupportedMetadata(message);
}

function routePath(value) {
  if (typeof value !== "string" || !value.startsWith("/") || value.length > 2048 || /[?#\\]/.test(value)) {
    fail("Use a bounded, static route pathname without a query or fragment.");
  }
  const segments = value.split("/").filter(Boolean).map((part) => {
    let decoded;
    try { decoded = decodeURIComponent(part); } catch { fail("Invalid route encoding."); }
    if ([".", ".."].includes(decoded) || /[/\\\u0000-\u001f]/.test(decoded)) fail("Unsafe route pathname.");
    return encodeURIComponent(decoded);
  });
  return `/${segments.join("/")}`;
}

function inspectPath(path) {
  if (typeof path !== "string" || path.length > 500 || /[\\\u0000-\u001f]/.test(path)) fail("Unsafe source path.");
  const parts = path.split("/");
  if (parts.some((part) => !part || [".", ".."].includes(part))) fail("Unsafe source path.");
  const start = parts[0] === "app" ? 1 : parts[0] === "src" && parts[1] === "app" ? 2 : 0;
  if (!start || !/^(page|layout)\.tsx?$/.test(parts.at(-1))) fail("Only App Router TypeScript pages and layouts are accepted.");
  const directories = parts.slice(start, -1);
  const complexRouting = directories.some((part) => part.startsWith("@") || /^\(\.{1,3}\)/.test(part));
  const unsupported = directories.some((part) => /[\[\]@]/.test(part) || part.startsWith("_") || /^\(\.{1,3}\)/.test(part));
  const segments = directories.filter((part) => !/^\([^()]+\)$/.test(part));
  if (segments.some((part) => /[()]/.test(part))) return { unsupported: true };
  return { root: parts.slice(0, start).join("/"), directories, unsupported, complexRouting,
    route: `/${segments.map(encodeURIComponent).join("/")}`, kind: parts.at(-1).split(".")[0] };
}

function unwrap(node) {
  while (node && (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node))) {
    node = node.expression;
  }
  return node;
}

function exported(statement) {
  return statement.modifiers?.some((item) => item.kind === ts.SyntaxKind.ExportKeyword);
}

function nameText(name) {
  if (ts.isIdentifier(name) || ts.isStringLiteral(name)) return name.text;
  fail("Computed metadata properties require manual review.");
}

function bindingNames(name) {
  if (ts.isIdentifier(name)) return [name.text];
  return name.elements.flatMap((item) => ts.isOmittedExpression(item) ? [] : bindingNames(item.name));
}

function inspectSource(path, text) {
  const ast = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true,
    path.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  if (ast.parseDiagnostics.length) fail("Source parsing failed; manual review is required.");
  let object;
  let metadataBinding;
  let reservedName = false;
  for (const statement of ast.statements) {
    if (ts.isExpressionStatement(statement) && ts.isStringLiteral(statement.expression) && statement.expression.text === "use client") {
      fail("Client Components require manual review.");
    }
    if (statement.name?.text === "generateMetadata") fail("Dynamic metadata requires manual review.");
    if (statement.name?.text === "metadata") fail("An existing metadata binding requires manual review.");
    if (ts.isExportDeclaration(statement)) {
      if (!statement.exportClause) fail("Wildcard exports require manual review.");
      if (ts.isNamedExports(statement.exportClause) && statement.exportClause.elements.some((item) =>
        [item.name.text, item.propertyName?.text].some((name) => ["metadata", "generateMetadata"].includes(name)))) {
        fail("Re-exported metadata requires manual review.");
      }
    }
    if (ts.isImportDeclaration(statement) && statement.importClause) {
      const clause = statement.importClause;
      const bindings = clause.namedBindings;
      if (clause.name?.text === "metadata" || bindings?.name?.text === "metadata" ||
        bindings?.elements?.some((item) => item.name.text === "metadata")) reservedName = true;
    }
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      const names = bindingNames(declaration.name);
      if (names.includes("generateMetadata")) fail("Dynamic metadata requires manual review.");
      if (!names.includes("metadata")) continue;
      if (reservedName || object || !ts.isIdentifier(declaration.name) || !exported(statement) ||
        !(statement.declarationList.flags & ts.NodeFlags.Const)) fail("Metadata must be one exported static const object.");
      reservedName = true;
      metadataBinding = declaration.name;
      object = unwrap(declaration.initializer);
      if (!object || !ts.isObjectLiteralExpression(object)) fail("Metadata must be a static object literal.");
    }
  }
  if (reservedName && !object) fail("An existing metadata binding requires manual review.");
  if (metadataBinding) {
    const inspectReference = (node) => {
      if (ts.isIdentifier(node) && node.text === "metadata" && node !== metadataBinding) {
        fail("Metadata references or mutations require manual review.");
      }
      ts.forEachChild(node, inspectReference);
    };
    inspectReference(ast);
  }
  const properties = new Map();
  for (const property of object?.properties ?? []) {
    if (!ts.isPropertyAssignment(property)) fail("Metadata spreads, methods and shorthand properties require manual review.");
    const name = nameText(property.name);
    if (properties.has(name)) fail("Duplicate metadata properties require manual review.");
    properties.set(name, property);
  }
  const values = {};
  for (const field of ["title", "description"]) {
    const value = unwrap(properties.get(field)?.initializer);
    if (!value) continue;
    if (!ts.isStringLiteral(value) && !ts.isNoSubstitutionTemplateLiteral(value)) {
      fail(field === "title" ? "Dynamic titles and title templates require manual review." : "Dynamic descriptions require manual review.");
    }
    values[field] = value.text;
  }
  return { ast, object, properties, values };
}

function literal(value) {
  return JSON.stringify(value).replaceAll("\u2028", "\\u2028").replaceAll("\u2029", "\\u2029");
}

function editSource(text, inspected, edits) {
  const { ast, object, properties } = inspected;
  const ranges = [];
  const additions = [];
  for (const field of ["title", "description"]) {
    if (!(field in edits)) continue;
    const property = properties.get(field);
    if (property) ranges.push({ start: property.initializer.getStart(ast), end: property.initializer.end, value: literal(edits[field]) });
    else additions.push(`  ${field}: ${literal(edits[field])},`);
  }
  if (object && additions.length) {
    const last = object.properties.at(-1);
    const closing = object.end - 1;
    let prefix = "";
    if (last && !object.properties.hasTrailingComma) {
      if (last.end === closing) prefix = ",";
      else ranges.push({ start: last.end, end: last.end, value: "," });
    }
    ranges.push({ start: closing, end: closing, value: `${prefix}\n${additions.join("\n")}\n` });
  } else if (!object) {
    // Insert after directives/imports, retaining all original JSX and unrelated declarations byte for byte.
    let position = 0;
    for (const statement of ast.statements) {
      if (ts.isImportDeclaration(statement) || ts.isExpressionStatement(statement) && ts.isStringLiteral(statement.expression)) position = statement.end;
      else break;
    }
    ranges.push({ start: position, end: position, value: `\n\nexport const metadata = {\n${additions.join("\n")}\n};\n` });
  }
  ranges.sort((a, b) => b.start - a.start || b.end - a.end);
  let result = text;
  for (const range of ranges) result = result.slice(0, range.start) + range.value + result.slice(range.end);
  return result;
}

export function generateMetadataPatch(input) {
  if (!input || typeof input !== "object" || Array.isArray(input) || !input.files || typeof input.files !== "object" || Array.isArray(input.files)) fail("Invalid source inventory.");
  const files = Object.entries(input.files);
  if (!files.length || files.length > MAX_FILES || Buffer.byteLength(JSON.stringify(input)) > MAX_INPUT_BYTES) fail("Source inventory exceeds the bounded limit.");
  const inventory = new Map();
  const routes = new Map();
  for (const [path, text] of files) {
    if (typeof text !== "string" || Buffer.byteLength(text) > MAX_FILE_BYTES) fail("Source file exceeds the bounded limit.");
    const details = inspectPath(path);
    inventory.set(path, { ...details, text });
    if (details.kind === "page" && !details.unsupported) {
      const existing = routes.get(details.route) ?? [];
      existing.push(path);
      routes.set(details.route, existing);
    }
  }
  const roots = new Set([...inventory.values()].map((item) => item.root).filter(Boolean));
  if (roots.size > 1) fail("Multiple App Router roots require manual review.");
  if ([...inventory.values()].some((item) => item.complexRouting)) fail("Parallel and intercepted routes require manual review.");
  if (!Array.isArray(input.edits) || !input.edits.length || input.edits.length > 3) fail("Select between one and three pages.");
  const seen = new Set();
  const changes = [];
  const mappings = [];
  for (const edit of input.edits) {
    if (!edit || typeof edit !== "object" || Object.keys(edit).some((key) => !["url", "route", "title", "description"].includes(key))) fail("Invalid metadata edit.");
    const route = routePath(edit.route);
    let url;
    try { url = new URL(edit.url); } catch { fail("Invalid page URL."); }
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash || routePath(url.pathname) !== route) fail("The page URL must match its static route.");
    if (!("title" in edit) && !("description" in edit)) fail("Choose a title or description change.");
    for (const [field, maximum] of [["title", 120], ["description", 320]]) {
      if (field in edit && (typeof edit[field] !== "string" || !edit[field].trim() || edit[field].length > maximum || /[\u0000-\u001f\u007f]/.test(edit[field]))) fail("Metadata text is empty, too long or contains control characters.");
    }
    const matches = routes.get(route) ?? [];
    if (matches.length !== 1) fail(matches.length ? "Ambiguous App Router mapping requires manual review." : "No supported static App Router page matches this URL.");
    const path = matches[0];
    if (seen.has(path)) fail("Each page may appear only once in a proposal.");
    seen.add(path);
    const page = inventory.get(path);
    const layoutPaths = [];
    for (let count = 0; count <= page.directories.length; count++) {
      const prefix = [page.root, ...page.directories.slice(0, count)].join("/");
      const candidates = ["tsx", "ts"].map((extension) => `${prefix}/layout.${extension}`).filter((candidate) => inventory.has(candidate));
      if (candidates.length > 1) fail("Ambiguous layout mapping requires manual review.");
      layoutPaths.push(...candidates);
    }
    const effective = { title: null, description: null };
    for (const layoutPath of layoutPaths) Object.assign(effective, inspectSource(layoutPath, inventory.get(layoutPath).text).values);
    const inspected = inspectSource(path, page.text);
    Object.assign(effective, inspected.values);
    if (["title", "description"].filter((field) => field in edit).every((field) => edit[field] === effective[field])) {
      fail("The selected metadata already matches the source.");
    }
    const after = editSource(page.text, inspected, edit);
    const updated = inspectSource(path, after);
    const expected = { ...effective, ...Object.fromEntries(["title", "description"].filter((field) => field in edit).map((field) => [field, edit[field]])) };
    for (const field of ["title", "description"]) {
      const observed = updated.values[field] ?? effective[field];
      if (observed !== expected[field]) fail("Metadata transformation could not be verified.");
    }
    if (after === page.text) fail("The selected metadata already matches the source.");
    changes.push({ path, before: page.text, after, old_title: effective.title, old_description: effective.description,
      title: expected.title, description: expected.description, url: edit.url, route });
    mappings.push({ url: edit.url, route, path });
  }
  return { changes, mappings };
}

async function main() {
  let text = "";
  for await (const chunk of process.stdin) {
    text += chunk;
    if (Buffer.byteLength(text) > MAX_INPUT_BYTES) fail("Source inventory exceeds the bounded limit.");
  }
  const result = generateMetadataPatch(JSON.parse(text));
  process.stdout.write(JSON.stringify({ ok: true, ...result }));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    const message = error instanceof UnsupportedMetadata ? error.message : "The trusted metadata helper could not process this source.";
    process.stdout.write(JSON.stringify({ ok: false, error: message }));
    process.exitCode = 1;
  });
}
