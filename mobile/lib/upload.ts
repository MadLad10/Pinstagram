/**
 * PUT a local file to a presigned URL, reporting progress (0..1).
 * fetch() has no upload progress events in React Native, so this uses XHR.
 */
export function uploadWithProgress(
  url: string,
  fileUri: string,
  contentType: string,
  onProgress: (fraction: number) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", contentType);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Upload failed (${xhr.status})`)));
    xhr.onerror = () => reject(new Error("Network error during upload"));
    // React Native's XHR accepts a { uri, type, name } object as a file body.
    xhr.send({ uri: fileUri, type: contentType, name: "upload" } as unknown as Blob);
  });
}
