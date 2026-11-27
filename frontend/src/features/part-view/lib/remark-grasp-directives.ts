import type { Root, Node } from "mdast";
import { visit } from "unist-util-visit";

const GRASP_DIRECTIVES = new Set(["widget", "image", "quiz"]);

interface DirectiveNode extends Node {
  type: "leafDirective" | "containerDirective" | "textDirective";
  name: string;
  attributes?: Record<string, string>;
  children?: Node[];
}

interface DataNode extends Node {
  type: string;
  data: {
    hProperties: {
      dataKey: string;
    };
  };
  children: Node[];
}

interface ParentWithChildren {
  children: Node[];
}

export function remarkGraspDirectives() {
  return (tree: Root) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    visit(tree as any, (node: any, index: number | undefined, parent: any) => {
      if (!parent || typeof index !== "number") return;

      const directive = node as DirectiveNode;
      const parentNode = parent as ParentWithChildren;

      if (
        directive.type === "leafDirective" ||
        directive.type === "containerDirective"
      ) {
        if (!GRASP_DIRECTIVES.has(directive.name)) {
          console.warn(`Unknown GRASP directive: ${directive.name}`);
          parentNode.children.splice(index, 1);
          return;
        }

        const key = directive.attributes?.ref || directive.attributes?.id;
        if (!key) {
          console.warn(
            `GRASP directive ${directive.name} missing required attribute (ref or id)`
          );
          parentNode.children.splice(index, 1);
          return;
        }

        const dataNode: DataNode = {
          type: "grasp-" + directive.name,
          data: {
            hProperties: {
              dataKey: key,
            },
          },
          children: [],
        };

        parentNode.children.splice(index, 1, dataNode);
        return;
      }

      // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
      if (directive.type === "textDirective") {
        if (GRASP_DIRECTIVES.has(directive.name)) {
          console.warn(
            `GRASP directive ${directive.name} used as text directive, removing`
          );
          parentNode.children.splice(index, 1);
          return;
        }
      }
    });
  };
}

export type { Root } from "mdast";
