'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import type { components } from '@/shared/api/schema';
type ImageOut = components['schemas']['ImageOut'];
import styles from './MarkdownRenderer.module.css';

interface MarkdownRendererProps {
  content: string;
  images?: Record<string, ImageOut>;
}

const MATH_BLOCK_CLASSES = ['math', 'math-display', 'katex-display'] as const;

// Type for hast element nodes passed by react-markdown
type HastElement = {
  properties?: Record<string, unknown>;
  tagName?: string;
  depth?: number | string;
  [key: string]: unknown;
};

/**
 * Custom component for rendering KaTeX math blocks and inline math.
 * rehype-katex adds specific classes that we can target.
 */
function MathComponent({ node, children, ...props }: React.HTMLAttributes<HTMLElement> & { node?: HastElement }) {
  const className = node?.properties?.className as string[] | undefined;
  const isDisplay = className?.some((c: string) => MATH_BLOCK_CLASSES.includes(c as 'math' | 'math-display' | 'katex-display')) ?? false;

  if (isDisplay) {
    return <div className={styles.mathBlock} {...props}>{children}</div>;
  }

  return <span className={styles.mathInline} {...props}>{children}</span>;
}

/**
 * Custom component for rendering code blocks with syntax highlighting.
 * rehype-highlight adds a `hljs` class and language-specific classes.
 */
function CodeBlockComponent({ node, children, ...props }: React.HTMLAttributes<HTMLElement> & { node?: HastElement }) {
  const className = node?.properties?.className as string[] | undefined;
  const language = className?.find((c: string) => c.startsWith('language-'))?.replace('language-', '') || '';
  const highlighted = node?.properties?.['data-highlighted'] === 'true';

  return (
    <div className={styles.codeBlockWrapper} data-language={language || 'plaintext'} {...props}>
      {language && <div className={styles.codeBlockLanguage}>{language}</div>}
      <pre className={styles.codeBlockPre}>
        <code className={`${styles.codeBlockCode} ${highlighted ? 'hljs' : ''}`}>{children}</code>
      </pre>
    </div>
  );
}

/**
 * Custom component for inline code.
 */
function InlineCodeComponent({ children, ...props }: React.HTMLAttributes<HTMLElement>) {
  return <code className={styles.inlineCode} {...props}>{children}</code>;
}

/**
 * Custom component for rendering tables with horizontal scroll on mobile.
 */
function TableComponent({ children, ...props }: React.HTMLAttributes<HTMLTableElement>) {
  return (
    <div className={styles.tableWrapper} {...props}>
      <table className={styles.table}>{children}</table>
    </div>
  );
}

/**
 * Custom component for rendering images.
 * Supports both regular markdown images and ImageOut references from the API.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ImageComponent({ node, ...props }: React.HTMLAttributes<HTMLImageElement> & { node?: any }) {
  // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
  const src = node?.properties?.src as string | undefined;
  // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
  const alt = node?.properties?.alt as string | undefined ?? '';
  // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
  const title = node?.properties?.title as string | undefined;

  // Check if this is a reference to an ImageOut by ID
  // Format: ![alt](image:{image_id}) or similar convention
  // For now, we render regular markdown images. ImageOut rendering is handled
  // separately in the DocumentPartView via the images prop.

  return (
    <figure className={styles.figure} {...props}>
      <img
        src={src ?? ''}
        alt={alt}
        title={title}
        loading="lazy"
        className={styles.image}
        onError={(e) => {
          e.currentTarget.style.display = 'none';
        }}
      />
      {(alt || title) && (
        <figcaption className={styles.figcaption}>
          {alt || title}
        </figcaption>
      )}
    </figure>
  );
}

/**
 * Custom component for rendering blockquotes.
 */
function BlockquoteComponent({ children, ...props }: React.HTMLAttributes<HTMLElement>) {
  return (
    <blockquote className={styles.blockquote} {...props}>
      {children}
    </blockquote>
  );
}

/**
 * Custom component for rendering horizontal rules.
 */
function HrComponent({ ...props }: React.HTMLAttributes<HTMLHRElement>) {
  return <hr className={styles.hr} {...props} />;
}

/**
 * Custom component for rendering headings.
 * react-markdown passes heading level as `depth` (1-6) as a direct prop.
 */
function HeadingComponent({ 
  node, 
  children, 
  depth, 
  level,
  ...props 
}: React.HTMLAttributes<HTMLHeadingElement> & { 
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  node?: any; 
  depth?: number | string; 
  level?: number | string 
}) {
  // react-markdown passes heading level as `depth` or `level` prop
  // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access, @typescript-eslint/no-unsafe-assignment
  const depthValue = depth ?? level ?? node?.depth ?? node?.properties?.level ?? node?.properties?.depth;
  const parsedLevel = typeof depthValue === 'number' ? depthValue : typeof depthValue === 'string' ? parseInt(depthValue, 10) : 1;
  const clampedLevel = Math.min(Math.max(parsedLevel || 1, 1), 6);
  const headingStyles = [
    null, // index 0 unused
    styles.heading1,
    styles.heading2,
    styles.heading3,
    styles.heading4,
    styles.heading5,
    styles.heading6,
  ];
  const Tag = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'][clampedLevel - 1] as 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  return React.createElement(Tag, { className: headingStyles[clampedLevel], ...props }, children);
}

const components = {
  // Math rendering
  'math-inline': MathComponent,
  'math-display': MathComponent,
  // Code blocks
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  code: ({ inline, node, children, ...props }: React.HTMLAttributes<HTMLElement> & { inline?: boolean; node?: any }) => {
    if (inline) {
      return <InlineCodeComponent {...props}>{children}</InlineCodeComponent>;
    }
    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
    return <CodeBlockComponent node={node} {...props}>{children}</CodeBlockComponent>;
  },
  // Tables
  table: TableComponent,
  // Images
  img: ImageComponent,
  // Blockquotes
  blockquote: BlockquoteComponent,
  // Horizontal rules
  hr: HrComponent,
  // Headings
  h1: HeadingComponent,
  h2: HeadingComponent,
  h3: HeadingComponent,
  h4: HeadingComponent,
  h5: HeadingComponent,
  h6: HeadingComponent,
};

export function MarkdownRenderer({ content, images }: MarkdownRendererProps) {
  return (
    <div className={styles.markdownContainer} data-testid="markdown-container">
      <ReactMarkdown
        components={components}
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[
          rehypeKatex,
          [rehypeHighlight, { ignoreMissing: true }],
        ]}
      >
        {content}
      </ReactMarkdown>

      {/* Render ImageOut images attached to this part */}
      {images && Object.keys(images).length > 0 && (
        <div className={styles.attachedImages} aria-label="Прикрепленные изображения">
          {Object.entries(images).map(([key, image]) => (
            <ImageOutRenderer key={key} image={image} refKey={key} />
          ))}
        </div>
      )}
    </div>
  );
}

interface ImageOutRendererProps {
  image: ImageOut;
  refKey: string;
}

function ImageOutRenderer({ image, refKey }: ImageOutRendererProps) {
  const [hasError, setHasError] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(true);

  if (!image.url) {
    return (
      <figure className={`${styles.figure} ${styles.imagePlaceholder}`} data-ref={refKey}>
        <div className={styles.imagePlaceholderContent} role="img" aria-label={image.caption || 'Изображение недоступно'}>
          <svg className={styles.imagePlaceholderIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <path d="M21 15l-5-5L5 21" />
          </svg>
          <span className={styles.imagePlaceholderText}>{image.caption || 'Изображение'}</span>
        </div>
        <figcaption className={styles.figcaption}>
          {image.caption || `Изображение ${refKey}`}
        </figcaption>
      </figure>
    );
  }

  return (
    <figure className={styles.figure} data-ref={refKey}>
      <img
        src={image.url}
        alt={image.caption || `Прикрепленное изображение ${refKey}`}
        loading="lazy"
        className={styles.image}
        onLoad={() => {
          setIsLoading(false);
        }}
        onError={() => {
          setHasError(true);
          setIsLoading(false);
        }}
        style={{ opacity: isLoading ? 0 : 1, transition: 'opacity 0.3s ease' }}
      />
      {isLoading && (
        <div className={styles.imageLoading} role="status" aria-label="Загрузка изображения...">
          <div className={styles.loadingSpinner} />
        </div>
      )}
      {hasError && (
        <div className={styles.imageError} role="alert">
          <svg className={styles.errorIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>Не удалось загрузить изображение</span>
        </div>
      )}
      {(image.caption && !hasError) && (
        <figcaption className={styles.figcaption}>{image.caption}</figcaption>
      )}
    </figure>
  );
}

export type { MarkdownRendererProps };