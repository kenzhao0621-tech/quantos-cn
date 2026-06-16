import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile, chmod } from "node:fs/promises";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..");

/** Storage state lives outside tracked source under playwright/.auth/ (gitignored). */
export function defaultAuthStorageRoot(): string {
  return resolve(REPO_ROOT, "playwright", ".auth");
}

export function storageStatePathForTarget(
  targetId: string,
  root: string = defaultAuthStorageRoot(),
): string {
  const safeId = targetId.replace(/[^a-zA-Z0-9._-]/g, "_");
  return join(root, `${safeId}.json`);
}

export interface SessionMetadata {
  targetId: string;
  storageStatePath: string;
  checksumSha256: string;
  updatedAt: string;
  bytes: number;
}

export async function ensureAuthStorageDir(root: string = defaultAuthStorageRoot()): Promise<string> {
  await mkdir(root, { recursive: true, mode: 0o700 });
  return root;
}

export function checksumForContent(content: string | Buffer): string {
  return createHash("sha256").update(content).digest("hex");
}

export async function saveStorageStateMetadata(
  targetId: string,
  storageStateJson: string,
  root: string = defaultAuthStorageRoot(),
): Promise<SessionMetadata> {
  const dir = await ensureAuthStorageDir(root);
  const storageStatePath = storageStatePathForTarget(targetId, dir);
  await writeFile(storageStatePath, storageStateJson, { encoding: "utf8", mode: 0o600 });
  await chmod(storageStatePath, 0o600);

  const checksumSha256 = checksumForContent(storageStateJson);
  const metadata: SessionMetadata = {
    targetId,
    storageStatePath,
    checksumSha256,
    updatedAt: new Date().toISOString(),
    bytes: Buffer.byteLength(storageStateJson, "utf8"),
  };

  const metadataPath = join(dir, `${targetId.replace(/[^a-zA-Z0-9._-]/g, "_")}.meta.json`);
  await writeFile(metadataPath, JSON.stringify(metadata, null, 2), {
    encoding: "utf8",
    mode: 0o600,
  });
  await chmod(metadataPath, 0o600);

  return metadata;
}

export async function loadSessionMetadata(
  targetId: string,
  root: string = defaultAuthStorageRoot(),
): Promise<SessionMetadata | null> {
  const metadataPath = join(root, `${targetId.replace(/[^a-zA-Z0-9._-]/g, "_")}.meta.json`);
  try {
    const raw = await readFile(metadataPath, "utf8");
    return JSON.parse(raw) as SessionMetadata;
  } catch {
    return null;
  }
}

export async function verifyStorageStateChecksum(
  metadata: SessionMetadata,
): Promise<boolean> {
  try {
    const raw = await readFile(metadata.storageStatePath, "utf8");
    return checksumForContent(raw) === metadata.checksumSha256;
  } catch {
    return false;
  }
}

/** Metadata for logs — never includes storage state contents. */
export function publicSessionMetadata(metadata: SessionMetadata): SessionMetadata {
  return { ...metadata };
}
