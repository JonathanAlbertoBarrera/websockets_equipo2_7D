// Cifrado asimétrico (RSA-OAEP con SHA-256)
export const asymmetricEncryption = {
  publicKey: null,
  privateKey: null,

  async initialize() {
    const keyPair = await window.crypto.subtle.generateKey(
      {
        name: "RSA-OAEP",
        modulusLength: 2048,
        publicExponent: new Uint8Array([1, 0, 1]),
        hash: "SHA-256"
      },
      true,
      ["encrypt", "decrypt"]
    );

    this.publicKey = keyPair.publicKey;
    this.privateKey = keyPair.privateKey;
    return true;
  },

  async exportPublicKey() {
    const exported = await window.crypto.subtle.exportKey("spki", this.publicKey);
    const exportedAsString = String.fromCharCode(...new Uint8Array(exported));
    const exportedAsBase64 = btoa(exportedAsString);
    return `-----BEGIN PUBLIC KEY-----\n${exportedAsBase64.match(/.{1,64}/g).join('\n')}\n-----END PUBLIC KEY-----`;
  },

  async encrypt(text, publicKeyPem) {
    const binaryDer = Uint8Array.from(atob(publicKeyPem
      .replace(/-----.*-----/g, '')
      .replace(/\s/g, '')
    ), c => c.charCodeAt(0));

    const importedKey = await window.crypto.subtle.importKey(
      "spki",
      binaryDer.buffer,
      { name: "RSA-OAEP", hash: "SHA-256" },
      false,
      ["encrypt"]
    );

    const encoded = new TextEncoder().encode(text);
    const encrypted = await window.crypto.subtle.encrypt(
      { name: "RSA-OAEP" },
      importedKey,
      encoded
    );

    return btoa(String.fromCharCode(...new Uint8Array(encrypted)));
  },

  async decrypt(encryptedBase64) {
    const encrypted = Uint8Array.from(atob(encryptedBase64), c => c.charCodeAt(0));
    const decrypted = await window.crypto.subtle.decrypt(
      { name: "RSA-OAEP" },
      this.privateKey,
      encrypted
    );
    return new TextDecoder().decode(decrypted);
  }
};