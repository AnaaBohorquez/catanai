/** Lado mayor de la foto que se envía. El backend reduce de todos modos a 1400 px. */
const LADO_MAXIMO = 1600;
const CALIDAD_JPEG = 0.85;

/**
 * Reduce la foto en el navegador antes de enviarla: una foto de celular pesa unos
 * 5 MB y tarda en subir con datos móviles; reducida pesa unos 300 KB.
 *
 * `imageOrientation: 'from-image'` aplica la rotación que el teléfono guarda en la
 * foto (EXIF): sin eso, una foto vertical llegaría acostada.
 */
export async function reducirFoto(archivo: File): Promise<Blob> {
  const imagen = await createImageBitmap(archivo, { imageOrientation: 'from-image' });
  const escala = Math.min(1, LADO_MAXIMO / Math.max(imagen.width, imagen.height));
  const lienzo = document.createElement('canvas');
  lienzo.width = Math.round(imagen.width * escala);
  lienzo.height = Math.round(imagen.height * escala);
  lienzo.getContext('2d')?.drawImage(imagen, 0, 0, lienzo.width, lienzo.height);
  imagen.close();
  return new Promise((resolver, rechazar) =>
    lienzo.toBlob(
      (blob) => (blob ? resolver(blob) : rechazar(new Error('No se pudo procesar la imagen'))),
      'image/jpeg',
      CALIDAD_JPEG,
    ),
  );
}
