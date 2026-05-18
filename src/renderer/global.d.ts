interface DataInfo {
  loaded?: boolean;
  source: string;
  rows: number;
  cols: number;
  columns: string[];
  dtypes?: Record<string, string>;
  null_counts?: Record<string, number>;
  unique_counts?: Record<string, number>;
}

interface ElectronApi {
  getBackendPort: () => Promise<number>;
  readClipboardText: () => Promise<string>;
  openFile: (filters?: unknown[]) => Promise<string | null>;
  saveFile: (defaultName?: string, filters?: unknown[]) => Promise<string | null>;
  readFile: (filePath: string) => Promise<BufferSource>;
  writeFile: (filePath: string, data: ArrayBuffer) => Promise<boolean>;
  onUpdateAvailable: (cb: (info: { version: string; releaseDate?: string; releaseNotes?: string }) => void) => void;
  onUpdateDownloaded: (cb: (info: { version: string }) => void) => void;
  onUpdateError: (cb: (error: string) => void) => void;
  onDownloadProgress: (cb: (progress: unknown) => void) => void;
  installUpdate: () => void;
  platform: string;
  getVersion: () => Promise<string>;
}

interface Window {
  electronAPI?: ElectronApi;
}

declare const Plotly: any;
declare const Papa: any;

interface Element {
  value?: string;
  checked?: boolean;
  disabled?: boolean;
  required?: boolean;
  data?: unknown;
  style?: CSSStyleDeclaration;
  dataset?: DOMStringMap;
  options: HTMLOptionsCollection;
  selectedOptions: HTMLCollectionOf<HTMLOptionElement>;
}

interface EventTarget {
  value?: string;
  checked?: boolean;
  closest?: (selector: string) => Element | null;
}
