import { lstat, readdir } from "node:fs/promises";
import { isAbsolute, relative, resolve, sep } from "node:path";

function toPosix(path) {
  return path.split(sep).join("/");
}

export async function mapDirectoryResources({
  resourceRoot,
  sourceDirectory,
  destinationDirectory,
}) {
  const root = resolve(resourceRoot);
  const source = resolve(sourceDirectory);
  const destination = destinationDirectory.replaceAll("\\", "/").replace(/\/+$/, "");
  if (
    !destination
    || isAbsolute(destination)
    || destination.split("/").some((part) => part === ".." || part === ".")
  ) {
    throw new Error("Installer resource destination must be a safe relative path.");
  }
  const sourceInfo = await lstat(source);
  if (!sourceInfo.isDirectory() || sourceInfo.isSymbolicLink()) {
    throw new Error("Installer resource source must be a real directory.");
  }

  const mapping = {};
  async function visit(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const file = resolve(directory, entry.name);
      if (entry.isSymbolicLink()) {
        throw new Error(`Installer resource tree cannot contain symbolic links: ${entry.name}`);
      }
      if (entry.isDirectory()) {
        await visit(file);
        continue;
      }
      if (!entry.isFile()) {
        throw new Error(`Installer resource tree contains an unsupported entry: ${entry.name}`);
      }

      const sourcePath = toPosix(relative(root, file));
      const nestedPath = toPosix(relative(source, file));
      if (!nestedPath || nestedPath === ".." || nestedPath.startsWith("../")) {
        throw new Error("Installer resource file escaped its declared source directory.");
      }
      if (Object.hasOwn(mapping, sourcePath)) {
        throw new Error("Installer resource mapping contains a duplicate source file.");
      }
      mapping[sourcePath] = `${destination}/${nestedPath}`;
    }
  }

  await visit(source);
  if (Object.keys(mapping).length === 0) {
    throw new Error("Installer resource source directory is empty.");
  }
  return mapping;
}
