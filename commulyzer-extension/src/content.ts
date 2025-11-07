import { loadArtifacts } from './model/artifacts';
import { scoreText } from './model/inference';

type Artifacts = Awaited<ReturnType<typeof loadArtifacts>>;

const processedNodes = new WeakSet<Node>();
let observer: MutationObserver | undefined;
let scheduled = false;
let artifactsPromise: Promise<Artifacts> | undefined;

function splitSentences(text: string): string[] {
  const matches = text.match(/[^.!?\n\r]+[.!?\u2026]*\s*/g);
  if (!matches) {
    return [text];
  }
  return matches;
}

function injectStyles(): void {
  if (document.getElementById('commulyzer-style')) {
    return;
  }
  const style = document.createElement('style');
  style.id = 'commulyzer-style';
  style.textContent = `
    .commulyzer-mask {
      background-color: rgba(248, 113, 113, 0.15);
      color: #b91c1c;
      font-style: italic;
      border-radius: 0.25rem;
      padding: 0.1rem 0.2rem;
    }
  `;
  document.head.appendChild(style);
}

async function getArtifacts(): Promise<Artifacts> {
  if (!artifactsPromise) {
    artifactsPromise = loadArtifacts();
  }
  return artifactsPromise;
}

function createPlaceholder(labels: string[], trailingWhitespace: string): Node {
  const span = document.createElement('span');
  span.className = 'commulyzer-mask';
  span.setAttribute('data-commulyzer', 'placeholder');
  const reason = labels.join(', ');
  span.textContent = `<this sentence was removed for ${reason}>${trailingWhitespace}`;
  processedNodes.add(span);
  return span;
}

function analyseTextNode(node: Text, artifacts: Artifacts): void {
  if (processedNodes.has(node)) {
    return;
  }

  const original = node.textContent ?? '';
  if (!original.trim()) {
    processedNodes.add(node);
    return;
  }

  const sentences = splitSentences(original);
  let modified = false;
  const fragments: Node[] = [];

  sentences.forEach((segment) => {
    const trimmed = segment.trim();
    if (!trimmed) {
      const textNode = document.createTextNode(segment);
      processedNodes.add(textNode);
      fragments.push(textNode);
      return;
    }

    const result = scoreText(trimmed, artifacts);
    if (result.activeLabels.length === 0) {
      const cleanNode = document.createTextNode(segment);
      processedNodes.add(cleanNode);
      fragments.push(cleanNode);
      return;
    }

    modified = true;
    const trailing = segment.match(/\s+$/)?.[0] ?? '';
    fragments.push(createPlaceholder(result.activeLabels, trailing));
  });

  if (!modified) {
    processedNodes.add(node);
    return;
  }

  const fragment = document.createDocumentFragment();
  fragments.forEach((child) => {
    fragment.appendChild(child);
  });

  const parent = node.parentNode;
  if (!parent) {
    return;
  }
  parent.replaceChild(fragment, node);
}

function walkAndAnalyse(root: Node, artifacts: Artifacts): void {
  const treeWalker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (processedNodes.has(node)) {
        return NodeFilter.FILTER_REJECT;
      }
      const parent = node.parentElement;
      if (!parent) {
        return NodeFilter.FILTER_REJECT;
      }
      if (parent.closest('[data-commulyzer="placeholder"]')) {
        return NodeFilter.FILTER_REJECT;
      }
      const tagName = parent.tagName;
      if (
        tagName === 'SCRIPT' ||
        tagName === 'STYLE' ||
        tagName === 'NOSCRIPT' ||
        tagName === 'TEXTAREA' ||
        tagName === 'INPUT'
      ) {
        return NodeFilter.FILTER_REJECT;
      }
      if (parent.isContentEditable) {
        return NodeFilter.FILTER_REJECT;
      }
      const text = node.textContent ?? '';
      if (!/\w/.test(text)) {
        return NodeFilter.FILTER_SKIP;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });

  let current: Node | null = treeWalker.nextNode();
  while (current) {
    analyseTextNode(current as Text, artifacts);
    current = treeWalker.nextNode();
  }
}

async function performScan(): Promise<void> {
  scheduled = false;
  try {
    const artifacts = await getArtifacts();
    const body = document.body;
    if (body) {
      walkAndAnalyse(body, artifacts);
    }
  } catch (error) {
    console.error('Commulyzer failed to load artifacts:', error);
    observer?.disconnect();
  }
}

function scheduleScan(): void {
  if (scheduled) {
    return;
  }
  scheduled = true;
  setTimeout(() => {
    void performScan();
  }, 250);
}

function startObserver(): void {
  if (observer) {
    observer.disconnect();
  }
  observer = new MutationObserver((mutations) => {
    const relevant = mutations.some((mutation) => {
      if (mutation.type === 'characterData') {
        return true;
      }
      return mutation.addedNodes.length > 0;
    });
    if (relevant) {
      scheduleScan();
    }
  });
  observer.observe(document.body, {
    childList: true,
    characterData: true,
    subtree: true,
  });
}

function init(): void {
  if (!document.body) {
    return;
  }
  injectStyles();
  scheduleScan();
  startObserver();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true });
} else {
  init();
}
