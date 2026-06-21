const MAX_SOURCE_BYTES = 12 * 1024 * 1024;
const MAX_OUTPUT_BYTES = 750 * 1024;
const MAX_DIMENSION = 1600;
const MIN_DIMENSION = 720;
const INITIAL_QUALITY = 0.78;
const MIN_QUALITY = 0.5;

const approximateDataUrlBytes = (source: string): number => {
    const commaIndex = source.indexOf(',');
    if (commaIndex < 0) return source.length;
    return Math.ceil((source.length - commaIndex - 1) * 0.75);
};

const readAsDataUrl = (blob: Blob): Promise<string> =>
    new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(new Error('Could not read the selected image.'));
        reader.readAsDataURL(blob);
    });

const loadImage = (source: string): Promise<HTMLImageElement> =>
    new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error('The selected image could not be decoded.'));
        image.src = source;
    });

const canvasToBlob = (
    canvas: HTMLCanvasElement,
    quality: number,
): Promise<Blob> =>
    new Promise((resolve, reject) => {
        canvas.toBlob(
            blob => blob
                ? resolve(blob)
                : reject(new Error('The browser could not compress this image.')),
            'image/webp',
            quality,
        );
    });

/**
 * Resize and compress an image into a bounded WebP data URL.
 *
 * Venue images are currently stored inline in the reading-room record. Keeping
 * each image below ~750 KB prevents multi-image onboarding saves from becoming
 * tens of megabytes and timing out through Cloud Run.
 */
export async function compressImageDataUrl(source: string): Promise<string> {
    if (!source.startsWith('data:image/')) return source;
    if (approximateDataUrlBytes(source) <= MAX_OUTPUT_BYTES) return source;

    const image = await loadImage(source);
    const longestSide = Math.max(image.naturalWidth, image.naturalHeight);
    let scale = Math.min(1, MAX_DIMENSION / longestSide);
    let quality = INITIAL_QUALITY;
    let output: Blob | undefined;

    for (let attempt = 0; attempt < 7; attempt += 1) {
        const width = Math.max(1, Math.round(image.naturalWidth * scale));
        const height = Math.max(1, Math.round(image.naturalHeight * scale));
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;

        const context = canvas.getContext('2d');
        if (!context) throw new Error('Image processing is unavailable in this browser.');

        context.imageSmoothingEnabled = true;
        context.imageSmoothingQuality = 'high';
        context.drawImage(image, 0, 0, width, height);
        output = await canvasToBlob(canvas, quality);

        if (output.size <= MAX_OUTPUT_BYTES) break;

        if (quality > MIN_QUALITY) {
            quality = Math.max(MIN_QUALITY, quality - 0.1);
        } else {
            const currentLongestSide = Math.max(width, height);
            if (currentLongestSide <= MIN_DIMENSION) break;
            scale *= 0.8;
        }
    }

    if (!output) throw new Error('Image compression failed.');
    return readAsDataUrl(output);
}

export async function compressVenueImage(file: File): Promise<string> {
    if (!file.type.startsWith('image/')) {
        throw new Error(`${file.name} is not a supported image file.`);
    }
    if (file.size > MAX_SOURCE_BYTES) {
        throw new Error(`${file.name} is larger than 12 MB.`);
    }

    return compressImageDataUrl(await readAsDataUrl(file));
}

export async function compactVenueImages(images: string[]): Promise<string[]> {
    const compacted: string[] = [];
    // Process sequentially to avoid decoding several full-resolution camera
    // images into memory at the same time on mobile devices.
    for (const image of images) {
        compacted.push(await compressImageDataUrl(image));
    }
    return compacted;
}
