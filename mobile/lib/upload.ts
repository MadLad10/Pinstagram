import { Platform } from "react-native";

export interface PreparedUpload {
  size: number;
  /** PUT the file to a presigned URL, reporting progress (0..1). */
  send: (url: string, contentType: string, onProgress: (fraction: number) => void) => Promise<void>;
}

/**
 * Native: React Native's XHR accepts a { uri, type, name } file reference.
 * Web: the picker returns a blob:/data: URL, so read it into a real Blob.
 * XHR (not fetch) is used on both because fetch has no upload progress events.
 */
export async function prepareUpload(uri: string, knownSize?: number | null): Promise<PreparedUpload> {
  let body: unknown;
  let size = knownSize ?? 0;
  if (Platform.OS === "web") {
    const blob = await fetch(uri).then((r) => r.blob());
    body = blob;
    size = blob.size;
  }

  return {
    size: size || 1,
    send: (url, contentType, onProgress) =>
      new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("PUT", url);
        xhr.setRequestHeader("Content-Type", contentType);
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) onProgress(e.loaded / e.total);
        };
        xhr.onload = () =>
          xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Upload failed (${xhr.status})`));
        xhr.onerror = () => reject(new Error("Network error during upload"));
        xhr.send((body ?? { uri, type: contentType, name: "upload" }) as Blob);
      }),
  };
}
