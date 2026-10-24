import test from "node:test";
import assert from "node:assert/strict";
import { generateMetadataPatch, UnsupportedMetadata } from "./metadata.mjs";

const page = `export const metadata = { title: 'Before', description: 'Original description', robots: { index: true }, alternates: {canonical: '/about'} };\nexport default function Page() { return <main><h1>Unchanged content</h1></main>; }\n`;
const edit = { url: "https://example.com/about", route: "/about", title: "After", description: "Reviewed description" };

test("precise changes preserve JSX and unrelated metadata", () => {
  const result = generateMetadataPatch({ files: { "app/about/page.tsx": page }, edits: [edit] });
  assert.equal(result.changes.length, 1);
  const change = result.changes[0];
  assert.equal(change.path, "app/about/page.tsx");
  assert.equal(change.old_title, "Before");
  assert.equal(change.old_description, "Original description");
  assert.equal(change.after, page.replace("'Before'", '"After"').replace("'Original description'", '"Reviewed description"'));
});

test("inherited static metadata creates a page override in src/app and route groups", () => {
  const files = {
    "src/app/layout.tsx": "export const metadata = {title: 'Inherited title', description: 'Inherited description'}; export default function Root({children}) {return children}",
    "src/app/(marketing)/about/page.tsx": "import Link from 'next/link';\nexport default function Page() {return <main>About us</main>}",
  };
  const change = generateMetadataPatch({ files, edits: [edit] }).changes[0];
  assert.equal(change.old_title, "Inherited title");
  assert.equal(change.old_description, "Inherited description");
  assert.match(change.after, /export const metadata =/);
  assert.ok(change.after.endsWith("export default function Page() {return <main>About us</main>}"));
  assert.deepEqual(Object.keys(files), ["src/app/layout.tsx", "src/app/(marketing)/about/page.tsx"]);
});

test("partial field addition handles trailing commas and comments", () => {
  for (const metadata of ["{robots: {index: true}}", "{robots: {index: true},}", "{robots: {index: true} // preserved\n}", "{}"] ) {
    const change = generateMetadataPatch({ files: {"app/page.tsx": `export const metadata = ${metadata}; export default function Page(){return <main>Home</main>}`},
      edits: [{url: "https://example.com/", route: "/", description: "New description"}] }).changes[0];
    assert.equal(change.title, null);
    assert.equal(change.description, "New description");
    assert.match(change.after, /description: "New description"/);
    assert.equal(change.after.includes("// preserved"), metadata.includes("// preserved"));
  }
});

test("Unicode and code-like quotes stay string data", () => {
  const title = 'Café 🦉 "quoted" ${process.env.OPENAI_API_KEY} \\ end';
  const description = "München’s trusted guide </script><script>throw 'never'</script>";
  const result = generateMetadataPatch({ files: {"app/über/page.tsx": page}, edits: [{url: "https://example.com/%C3%BCber", route: "/über", title, description}] });
  assert.equal(result.changes[0].title, title);
  assert.equal(result.changes[0].description, description);
  assert.ok(result.changes[0].after.includes(JSON.stringify(title)));
});

test("type wrappers and string template literals are statically readable", () => {
  const source = "import type { Metadata } from 'next'; export const metadata: Metadata = ({title: `Before`} satisfies Metadata); export default function Page(){return <main>Home</main>}";
  const result = generateMetadataPatch({ files: {"app/about/page.tsx": source}, edits: [edit] });
  assert.equal(result.changes[0].old_title, "Before");
});

const unsupported = [
  ["client component", {"app/about/page.tsx": `"use client"; ${page}`}],
  ["dynamic metadata", {"app/about/page.tsx": "export async function generateMetadata(){return {title:'x'}}; export default function Page(){}"}],
  ["dynamic ancestor", {"app/layout.tsx": "export const generateMetadata = () => ({title:'x'});", "app/about/page.tsx": page}],
  ["title template ancestor", {"app/layout.tsx": "export const metadata = {title:{default:'Site', template:'%s | Site'}}", "app/about/page.tsx": page}],
  ["dynamic title", {"app/about/page.tsx": "const title = 'Before'; export const metadata = {title};"}],
  ["unresolved title", {"app/about/page.tsx": "export const metadata = {title: getTitle()};"}],
  ["spread", {"app/about/page.tsx": "export const metadata = {...other, title:'Before'};"}],
  ["computed", {"app/about/page.tsx": "export const metadata = {['title']:'Before'};"}],
  ["duplicate metadata", {"app/about/page.tsx": "export const metadata = {title:'a', title:'b'};"}],
  ["mutable metadata", {"app/about/page.tsx": "export let metadata = {title:'Before'};"}],
  ["re-export", {"app/about/page.tsx": "export {metadata} from './private'; export default function Page(){}"}],
  ["wildcard re-export", {"app/about/page.tsx": "export * from './private'; export default function Page(){}"}],
  ["metadata binding", {"app/about/page.tsx": "const metadata = {}; export default function Page(){}"}],
  ["metadata function binding", {"app/about/page.tsx": "function metadata(){}; export default function Page(){}"}],
  ["metadata mutation", {"app/about/page.tsx": page + "\nmetadata.title = getTitle();"}],
  ["metadata object assign", {"app/about/page.tsx": page + "\nObject.assign(metadata, other);"}],
  ["dynamic route", {"app/[slug]/page.tsx": page}],
  ["parallel route", {"app/@modal/about/page.tsx": page}],
  ["parallel ambiguity beside static page", {"app/@modal/about/page.tsx": page, "app/about/page.tsx": page}],
  ["interception", {"app/(.)about/page.tsx": page}],
  ["private folder", {"app/_private/about/page.tsx": page}],
  ["ambiguous groups", {"app/(one)/about/page.tsx": page, "app/(two)/about/page.tsx": page}],
  ["ambiguous root", {"app/about/page.tsx": page, "src/app/about/page.tsx": page}],
  ["ambiguous layouts", {"app/layout.tsx": "export const metadata = {}", "app/layout.ts": "export const metadata = {}", "app/about/page.tsx": page}],
  ["invalid syntax", {"app/about/page.tsx": "export const metadata = {title:"}],
  ["forbidden path", {"app/../about/page.tsx": page}],
  ["not a page", {"app/about/component.tsx": page}],
];
for (const [name, files] of unsupported) {
  test(`refuses ${name} as a whole`, () => {
    assert.throws(() => generateMetadataPatch({files, edits: [edit]}), UnsupportedMetadata);
  });
}

test("rejects mismatched routes, queries, duplicate selections and unchanged metadata", () => {
  const files = {"app/about/page.tsx": page};
  for (const edits of [
    [{...edit, url: "https://example.com/other"}], [{...edit, url: "https://example.com/about?view=1"}],
    [{...edit, route: "/a/%2f/about"}], [edit, edit], [{...edit, title: "Before", description: "Original description"}],
    [{...edit, title: ""}], [{...edit, description: "\ncontrol"}], [{...edit, title: "x".repeat(121)}],
  ]) assert.throws(() => generateMetadataPatch({files, edits}), UnsupportedMetadata);
});

test("bounds pages and source bytes", () => {
  assert.throws(() => generateMetadataPatch({files: {"app/about/page.tsx": "x".repeat(128 * 1024 + 1)}, edits:[edit]}), UnsupportedMetadata);
  assert.throws(() => generateMetadataPatch({files: {"app/about/page.tsx": page}, edits:[edit, edit, edit, edit]}), UnsupportedMetadata);
});
