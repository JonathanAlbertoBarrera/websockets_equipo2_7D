import CryptoJS from 'crypto-js';

// Cifrado asimétrico
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

// Cifrado simétrico
export const symmetricEncryption = {
  key: null,

  async initialize() {
    try {
      const response = await fetch('http://localhost:8000/symmetric-key');
      const data = await response.json();
      this.key = data.symmetric_key;
      return true;
    } catch (error) {
      console.error('Error obteniendo la clave simétrica:', error);
      return false;
    }
  },

  encrypt(message) {
    if (!this.key) {
      throw new Error('No symmetric key available');
    }
    const encrypted = CryptoJS.AES.encrypt(message, this.key);
    return encrypted.toString();
  },

  decrypt(encryptedMessage) {
    if (!this.key) {
      throw new Error('No symmetric key available');
    }
    const decrypted = CryptoJS.AES.decrypt(encryptedMessage, this.key);
    return decrypted.toString(CryptoJS.enc.Utf8);
  }
};