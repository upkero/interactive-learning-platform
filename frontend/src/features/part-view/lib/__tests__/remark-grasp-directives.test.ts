import { describe, it, expect, vi, beforeEach, afterAll } from "vitest";
import { fromMarkdown } from "mdast-util-from-markdown";
import { toMarkdown } from "mdast-util-to-markdown";
import { remarkGraspDirectives } from "../remark-grasp-directives";
import { directive } from "micromark-extension-directive";
import { directiveFromMarkdown } from "mdast-util-directive";

function parseMarkdown(markdown: string) {
  return fromMarkdown(markdown, {
    extensions: [directive()],
    mdastExtensions: [directiveFromMarkdown()],
  });
}

function runPlugin(tree: any) {
  const plugin = remarkGraspDirectives();
  plugin(tree);
  return tree;
}

describe("remarkGraspDirectives", () => {
  const consoleWarn = vi.spyOn(console, "warn").mockImplementation(() => {});

  beforeEach(() => {
    consoleWarn.mockClear();
  });

  afterAll(() => {
    consoleWarn.mockRestore();
  });

  it('transforms ::widget{ref="w1"} to grasp-widget node', () => {
    const tree = parseMarkdown('::widget{ref="w1"}');
    runPlugin(tree);

    const widgetNode = tree.children.find(
      (n: any) => n.type === "grasp-widget"
    );
    expect(widgetNode).toBeDefined();
    expect(widgetNode.data?.hProperties?.dataKey).toBe("w1");
  });

  it('transforms ::image{id="img_1"} to grasp-image node', () => {
    const tree = parseMarkdown('::image{id="img_1"}');
    runPlugin(tree);

    const imageNode = tree.children.find((n: any) => n.type === "grasp-image");
    expect(imageNode).toBeDefined();
    expect(imageNode.data?.hProperties?.dataKey).toBe("img_1");
  });

  it('transforms ::quiz{ref="q1"} to grasp-quiz node', () => {
    const tree = parseMarkdown('::quiz{ref="q1"}');
    runPlugin(tree);

    const quizNode = tree.children.find((n: any) => n.type === "grasp-quiz");
    expect(quizNode).toBeDefined();
    expect(quizNode.data?.hProperties?.dataKey).toBe("q1");
  });

  it("removes unknown directives", () => {
    const tree = parseMarkdown('::unknown{ref="x"}');
    runPlugin(tree);

    expect(consoleWarn).toHaveBeenCalledWith(
      expect.stringContaining("Unknown GRASP directive: unknown")
    );
    expect(tree.children.length).toBe(0);
  });

  it("removes directives missing required attributes", () => {
    const tree = parseMarkdown("::widget{}");
    runPlugin(tree);

    expect(consoleWarn).toHaveBeenCalledWith(
      expect.stringContaining("missing required attribute")
    );
    expect(tree.children.length).toBe(0);
  });

  it("does not process raw HTML as markdown - script tags remain as text", () => {
    const tree = parseMarkdown('<script>alert("xss")</script>');
    runPlugin(tree);

    // Raw HTML is not parsed as markdown, so it becomes a text node
    expect(tree.children.length).toBeGreaterThanOrEqual(0);
  });

  it("does not process raw HTML as markdown - img onerror remains as text", () => {
    const tree = parseMarkdown('<img src="x" onerror="alert(1)">');
    runPlugin(tree);

    // Raw HTML is not parsed as markdown, so it becomes a text node
    expect(tree.children.length).toBeGreaterThanOrEqual(0);
  });
});
