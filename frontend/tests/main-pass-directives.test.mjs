import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import remarkDirective from "remark-directive";
import remarkParse from "remark-parse";
import { unified } from "unified";

const fixture = new URL("../../backend/tests/support/fixtures/main_pass/directives.md", import.meta.url);
const parts = readFileSync(fixture, "utf8")
  .replaceAll("\r\n", "\n")
  .split(/<!-- case: ([\w-]+) -->\n/);
const cases = new Map();
for (let i = 1; i < parts.length; i += 2) {
  cases.set(parts[i], parts[i + 1].replace(/^\n+|\n+$/g, ""));
}
const parser = unified().use(remarkParse).use(remarkDirective);

function collect(node, types) {
  if (node.type.endsWith("Directive") || node.type === "code" || node.type === "inlineCode") {
    types.push([node.type, node.name ?? node.value]);
  }
  for (const child of node.children ?? []) {
    collect(child, types);
  }
}

const expected = {
  "leaf-before-code": [
    ["leafDirective", "widget"],
    ["code", ":quiz[example]"],
  ],
  "quote-list-before-code": [
    ["leafDirective", "quiz"],
    ["code", ":widget[example]"],
  ],
  "multiline-inline-code": [
    ["inlineCode", "a literal `\n:widget[label]\nend"],
    ["textDirective", "quiz"],
  ],
  "wide-container": [
    ["containerDirective", "widget"],
    ["code", ":widget[example]"],
  ],
  "nested-containers": [
    ["containerDirective", "note"],
    ["containerDirective", "quiz"],
  ],
  "unclosed-container": [["containerDirective", "image"]],
};

for (const [name, nodes] of Object.entries(expected)) {
  test("remark parses the shared main-pass example " + name, () => {
    assert.ok(cases.has(name), name);
    const actual = [];
    collect(parser.parse(cases.get(name)), actual);
    assert.deepEqual(actual, nodes);
  });
}

function links(node) {
  return [...(node.type === "link" ? [node.url] : []), ...(node.children ?? []).flatMap(links)];
}

for (const [name, count, urls] of [
  ["inline-syntax", 2, []],
  ["preserved-urls", 1, ["/guide/:quiz[example]", "https://example.com/:quiz[ok]"]],
]) {
  test("remark validates the shared cleanup example " + name, () => {
    const [source, cleaned] = cases.get(name).split("\n<!-- cleaned -->\n");
    const before = parser.parse(source);
    const after = parser.parse(cleaned);
    const originalNodes = [];
    const cleanedNodes = [];
    collect(before, originalNodes);
    collect(after, cleanedNodes);
    assert.deepEqual(originalNodes, Array.from({ length: count }, () => ["textDirective", "quiz"]));
    assert.deepEqual(cleanedNodes, []);
    assert.deepEqual(links(before), urls);
    assert.deepEqual(links(after), urls);
  });
}
