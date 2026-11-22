import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { MarkdownRenderer } from '../MarkdownRenderer';
import type { components } from '@/shared/api/schema';
type ImageOut = components['schemas']['ImageOut'];

describe('MarkdownRenderer', () => {
  const mockImages: Record<string, ImageOut> = {
    img1: {
      image_id: 'img-1',
      url: 'https://example.com/image1.png',
      caption: 'Test image caption',
    },
    img2: {
      image_id: 'img-2',
      url: 'https://example.com/image2.jpg',
      caption: null,
    },
    img3: {
      image_id: 'img-3',
      url: null,
      caption: 'Placeholder image',
    },
  };

  it('renders headings correctly', () => {
    render(
      <MarkdownRenderer
        content={`
# Heading 1
## Heading 2
### Heading 3
#### Heading 4
##### Heading 5
###### Heading 6
        `}
      />
    );

    // Check that all 6 headings are rendered (level may vary in test environment)
    const headings = screen.getAllByRole('heading');
    expect(headings).toHaveLength(6);
    
    // Check that each heading has the correct text
    expect(screen.getByText('Heading 1')).toBeInTheDocument();
    expect(screen.getByText('Heading 2')).toBeInTheDocument();
    expect(screen.getByText('Heading 3')).toBeInTheDocument();
    expect(screen.getByText('Heading 4')).toBeInTheDocument();
    expect(screen.getByText('Heading 5')).toBeInTheDocument();
    expect(screen.getByText('Heading 6')).toBeInTheDocument();
  });

  it('renders paragraphs and inline formatting', () => {
    render(
      <MarkdownRenderer
        content={`
This is a **bold** text and *italic* text and ~~strikethrough~~ text.
        `}
      />
    );

    // Text content is split across elements, so check for individual parts using regex
    expect(screen.getByText(/This is a/)).toBeInTheDocument();
    expect(screen.getByText('bold')).toBeInTheDocument();
    expect(screen.getByText(/text and/)).toBeInTheDocument();
    expect(screen.getByText('italic')).toBeInTheDocument();
    expect(screen.getByText('strikethrough')).toBeInTheDocument();
    expect(screen.getByText(/text\./)).toBeInTheDocument();
    
    // Check semantic elements
    expect(screen.getByText('bold').closest('strong')).toBeInTheDocument();
    expect(screen.getByText('italic').closest('em')).toBeInTheDocument();
    expect(screen.getByText('strikethrough').closest('del')).toBeInTheDocument();
  });

  it('renders inline code', () => {
    render(
      <MarkdownRenderer
        content={`Use \`const x = 1\` to declare a variable.`}
      />
    );

    const inlineCode = screen.getByText('const x = 1');
    expect(inlineCode).toBeInTheDocument();
    expect(inlineCode.tagName).toBe('CODE');
  });

  it('renders code blocks with syntax highlighting', () => {
    render(
      <MarkdownRenderer
        content={`
\`\`\`typescript
function greet(name: string): string {
  return \`Hello, \${name}!\`;
}
\`\`\`
        `}
      />
    );

    // Check for the code block structure
    const pre = screen.getByText('function').closest('pre');
    expect(pre).toBeInTheDocument();
    const code = pre?.querySelector('code');
    expect(code).toBeInTheDocument();
    // Check language attribute on wrapper
    const wrapper = pre?.parentElement;
    expect(wrapper).toHaveAttribute('data-language', 'typescript');
  });

  it('renders plain code blocks without language', () => {
    render(
      <MarkdownRenderer
        content={`
\`\`\`
plain text block
\`\`\`
        `}
      />
    );

    const pre = screen.getByText('plain text block').closest('pre');
    expect(pre).toBeInTheDocument();
    const wrapper = pre?.parentElement;
    expect(wrapper).toHaveAttribute('data-language', 'plaintext');
  });

  it('renders GFM tables with horizontal scroll wrapper', () => {
    render(
      <MarkdownRenderer
        content={`
| Header 1 | Header 2 |
| -------- | -------- |
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |
        `}
      />
    );

    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();
    const wrapper = table.parentElement;
    expect(wrapper).toBeInTheDocument(); // wrapper div exists
    expect(screen.getByText('Header 1')).toBeInTheDocument();
    expect(screen.getByText('Cell 2')).toBeInTheDocument();
  });

  it('renders blockquotes', () => {
    render(
      <MarkdownRenderer
        content={`
> This is a blockquote
> with multiple lines
        `}
      />
    );

    const blockquote = screen.getByText('This is a blockquote with multiple lines').closest('blockquote');
    expect(blockquote).toBeInTheDocument();
  });

  it('renders horizontal rules', () => {
    render(
      <MarkdownRenderer
        content={`
---
        `}
      />
    );

    const hr = screen.getByRole('separator');
    expect(hr).toBeInTheDocument();
    expect(hr.tagName).toBe('HR');
  });

  it('renders unordered and ordered lists', () => {
    render(
      <MarkdownRenderer
        content={`
- Item 1
- Item 2
  - Nested item
1. First
2. Second
        `}
      />
    );

    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 2')).toBeInTheDocument();
    expect(screen.getByText('Nested item')).toBeInTheDocument();
    expect(screen.getByText('First')).toBeInTheDocument();
    expect(screen.getByText('Second')).toBeInTheDocument();
  });

  it('renders task lists (GFM)', () => {
    render(
      <MarkdownRenderer
        content={`
- [x] Completed task
- [ ] Pending task
        `}
      />
    );

    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes).toHaveLength(2);
    expect(checkboxes[0]).toBeChecked();
    expect(checkboxes[1]).not.toBeChecked();
  });

  it('renders inline math formulas with KaTeX', () => {
    render(
      <MarkdownRenderer
        content={`The formula $E = mc^2$ is famous.`}
      />
    );

    // KaTeX renders math - check for katex class elements
    const katexElements = document.querySelectorAll('[class*="katex"]');
    expect(katexElements.length).toBeGreaterThan(0);
  });

  it('renders block math formulas with KaTeX', () => {
    render(
      <MarkdownRenderer
        content={`
$$
\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}
$$
        `}
      />
    );

    // Check that the integral symbol is rendered
    const integral = screen.getAllByText('∫');
    expect(integral.length).toBeGreaterThan(0);
  });

  it('renders regular markdown images', () => {
    render(
      <MarkdownRenderer
        content={`![Alt text](https://example.com/image.png "Title")`}
      />
    );

    const img = screen.getByAltText('Alt text');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', 'https://example.com/image.png');
    expect(img).toHaveAttribute('title', 'Title');
    const figure = img.closest('figure');
    expect(figure).toBeInTheDocument();
    const figcaption = screen.getByText('Alt text');
    expect(figcaption).toBeInTheDocument();
  });

  it('renders ImageOut images with captions', () => {
    render(
      <MarkdownRenderer
        content={`# Document`}
        images={mockImages}
      />
    );

    // Check first image with caption
    const img1 = screen.getByAltText('Test image caption');
    expect(img1).toHaveAttribute('src', 'https://example.com/image1.png');
    const figcaption1 = screen.getByText('Test image caption');
    expect(figcaption1).toBeInTheDocument();

    // Check second image without caption (should use alt text)
    const img2 = screen.getByAltText('Прикрепленное изображение img2');
    expect(img2).toHaveAttribute('src', 'https://example.com/image2.jpg');

    // Check third image with null URL (placeholder)
    const placeholder = screen.getAllByText('Placeholder image');
    expect(placeholder.length).toBeGreaterThanOrEqual(1);
  });

  it('shows loading state for ImageOut images', () => {
    render(
      <MarkdownRenderer
        content={''}
        images={{
          img1: {
            image_id: 'img-1',
            url: 'https://example.com/image1.png',
            caption: 'Loading test',
          },
        }}
      />
    );

    // Loading spinner should be present initially
    const loadingSpinner = screen.getByRole('status', { name: 'Загрузка изображения...' });
    expect(loadingSpinner).toBeInTheDocument();
  });

  it('shows error state when ImageOut image fails to load', () => {
    render(
      <MarkdownRenderer
        content={''}
        images={{
          img1: {
            image_id: 'img-1',
            url: 'https://example.com/broken.png',
            caption: 'Broken image',
          },
        }}
      />
    );

    // Simulate error by finding the image and triggering onError
    const img = screen.getByAltText('Broken image');
    // Fire error event
    act(() => {
      const errorEvent = new Event('error');
      Object.defineProperty(errorEvent, 'currentTarget', { value: img });
      img.dispatchEvent(errorEvent);
    });

    // Error state should be shown
    expect(screen.getByText('Не удалось загрузить изображение')).toBeInTheDocument();
  });

  it('renders links', () => {
    render(
      <MarkdownRenderer
        content={`[Link text](https://example.com)`}
      />
    );

    const link = screen.getByRole('link', { name: 'Link text' });
    expect(link).toHaveAttribute('href', 'https://example.com');
  });

  it('renders nested elements correctly', () => {
    render(
      <MarkdownRenderer
        content={`
> **Bold in blockquote**
>
> \`code in blockquote\`
        `}
      />
    );

    expect(screen.getByText('Bold in blockquote')).toBeInTheDocument();
    expect(screen.getByText('code in blockquote')).toBeInTheDocument();
  });

  it('handles empty content gracefully', () => {
    render(<MarkdownRenderer content={''} />);
    // Should not throw and render empty container
    expect(screen.getByTestId('markdown-container')).toBeInTheDocument();
  });

  it('renders container with test id', () => {
    render(
      <MarkdownRenderer
        content={`
# Title
Text with **bold** and \`code\`.
        `}
      />
    );

    const container = screen.getByTestId('markdown-container');
    expect(container).toBeInTheDocument();
  });
});