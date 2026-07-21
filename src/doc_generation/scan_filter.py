import os
import random
import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

def apply_scan_filter(input_pdf_path: str, output_pdf_path: str | None = None, 
                      intensity: str = "medium") -> str:
    """
    Convert a clean PDF into a scan-simulated PDF by rendering pages to images,
    applying noise, rotation, brightness adjustments, and assembling them back.

    Args:
        input_pdf_path: Path to the clean input PDF.
        output_pdf_path: Output path for the scanned PDF. If None, overwrites input.
        intensity: "light", "medium", or "heavy" — controls noise and rotation intensity.

    Returns:
        Path to the scan-simulated PDF.
    """
    if not os.path.exists(input_pdf_path):
        raise FileNotFoundError(f"Input PDF not found: {input_pdf_path}")

    # Set parameters based on intensity
    if intensity == "light":
        dpi = 220
        max_rotation = 0.4
        noise_sigma = 3.0
        brightness_range = (0.98, 1.02)
        tint_color = None
        blur_radius = 0.0
    elif intensity == "heavy":
        dpi = 150
        max_rotation = 1.4
        noise_sigma = 15.0
        brightness_range = (0.90, 1.10)
        tint_color = (252, 249, 235)  # Faded yellowed paper
        blur_radius = 0.6
    else:  # "medium"
        dpi = 180
        max_rotation = 0.8
        noise_sigma = 7.0
        brightness_range = (0.95, 1.05)
        tint_color = (255, 255, 248)  # Off-white cream paper
        blur_radius = 0.3

    doc = fitz.open(input_pdf_path)
    if len(doc) == 0:
        doc.close()
        return input_pdf_path

    processed_pages = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Render page to a high-quality pixmap
        pix = page.get_pixmap(dpi=dpi)
        
        # Load pixmap bytes into PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # 1. Apply slight random rotation to simulate sheet feeder misalignment
        angle = random.uniform(-max_rotation, max_rotation)
        img = img.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))

        # 2. Add subtle paper tint/coloration
        if tint_color:
            tint_layer = Image.new("RGB", img.size, tint_color)
            img = Image.blend(img, tint_layer, 0.12)  # Blend 12% of the tint color

        # Convert to numpy array for noise and brightness operations
        arr = np.array(img, dtype=np.float32)

        # 3. Apply brightness variation across the page (simulating scan bed shadow/uneven lighting)
        h, w, c = arr.shape
        x_grad = np.linspace(random.uniform(0.97, 1.0), random.uniform(1.0, 1.03), w)
        y_grad = np.linspace(random.uniform(0.97, 1.0), random.uniform(1.0, 1.03), h)
        grad = np.outer(y_grad, x_grad)
        grad_3d = np.repeat(grad[:, :, np.newaxis], 3, axis=2)
        arr = arr * grad_3d

        # 4. Add Gaussian noise to simulate CCD sensor noise / paper grain
        if noise_sigma > 0:
            noise = np.random.normal(0, noise_sigma, arr.shape)
            arr = arr + noise

        # Clip values to valid 0-255 range and convert back to uint8
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

        # 5. Apply brightness/contrast enhancement
        brightness_factor = random.uniform(*brightness_range)
        img = ImageEnhance.Brightness(img).enhance(brightness_factor)
        img = ImageEnhance.Contrast(img).enhance(1.05)  # Slightly boost contrast to make text pop

        # 6. Apply subtle blur (simulation of lens focus imperfection)
        if blur_radius > 0:
            img = img.filter(ImageFilter.GaussianBlur(blur_radius))

        # For heavy scanning, inject random dark speckles (dust/spots)
        if intensity == "heavy" and random.random() < 0.8:
            # Draw random tiny dust spots
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            num_spots = random.randint(10, 30)
            for _ in range(num_spots):
                x = random.randint(0, img.size[0] - 1)
                y = random.randint(0, img.size[1] - 1)
                r = random.randint(1, 2)
                draw.ellipse([x-r, y-r, x+r, y+r], fill=(random.randint(60, 140), random.randint(60, 140), random.randint(60, 140)))

        processed_pages.append(img)

    doc.close()

    # Determine final output destination
    final_output = output_pdf_path if output_pdf_path else input_pdf_path
    
    # Save the processed images together as a single PDF
    if processed_pages:
        processed_pages[0].save(final_output, save_all=True, append_images=processed_pages[1:], quality=85)

    return final_output
