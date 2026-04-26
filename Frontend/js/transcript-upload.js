// pdf.js setup
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('profile_pdf');
    const statusDiv = document.getElementById('profile-pdf-status');

    if (!fileInput || !statusDiv) return;

    fileInput.addEventListener('change', async (event) => {
        const file = event.target.files[0];
        if (!file) {
            statusDiv.innerHTML = 'No PDF selected.';
            statusDiv.style.color = '';
            return;
        }

        if (file.type !== 'application/pdf') {
            showError('Please upload a valid PDF file.');
            return;
        }

        statusDiv.innerHTML = '<span class="stream-text">Processing PDF<span class="blinking-dots"><span>.</span><span>.</span><span>.</span></span></span>';
        statusDiv.style.color = '';

        try {
            // 1. Read file as ArrayBuffer
            const arrayBuffer = await file.arrayBuffer();

            // 2. Load PDF document
            const pdf = await pdfjsLib.getDocument(arrayBuffer).promise;
            
            // 3. Get ONLY the first page
            const page = await pdf.getPage(1);

            // 4. Render to canvas at 300 DPI
            const viewport = page.getViewport({ scale: 300 / 72 });
            const srcCanvas = document.createElement('canvas');
            srcCanvas.width = viewport.width;
            srcCanvas.height = viewport.height;
            const srcCtx = srcCanvas.getContext('2d');
            
            await page.render({ canvasContext: srcCtx, viewport: viewport }).promise;

            // 5. Crop top 15%
            const cropHeight = srcCanvas.height * 0.85;
            const cropCanvas = document.createElement('canvas');
            cropCanvas.width = srcCanvas.width;
            cropCanvas.height = cropHeight;
            const cropCtx = cropCanvas.getContext('2d');

            // Draw the bottom 85% of the source canvas onto the destination canvas
            cropCtx.drawImage(
                srcCanvas,
                0, srcCanvas.height * 0.15, srcCanvas.width, cropHeight,
                0, 0, srcCanvas.width, cropHeight
            );

            // 6. Convert to blob
            const blob = await new Promise((resolve, reject) => {
                cropCanvas.toBlob((b) => {
                    if (b) resolve(b);
                    else reject(new Error('Failed to create image blob.'));
                }, 'image/jpeg', 0.95);
            });

            // 7. Upload to backend
            statusDiv.innerHTML = '<span class="stream-text">Uploading and extracting data<span class="blinking-dots"><span>.</span><span>.</span><span>.</span></span></span>';

            const formData = new FormData();
            // Append single cropped image
            formData.append('file', blob, 'transcript_page_1.jpg');

            const response = await fetch('/api/transcript/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                let errorMsg = 'Server error during upload.';
                try {
                    const result = await response.json();
                    if (result.detail) errorMsg = result.detail;
                } catch (e) {
                    const text = await response.text();
                    if (text) errorMsg = text;
                }
                throw new Error(errorMsg);
            }

            statusDiv.innerHTML = '✨ Transcript upload complete!';
            statusDiv.style.color = 'var(--accent)';

        } catch (error) {
            console.error('Transcript processing error:', error);
            showError(`Processing failed: ${error.message}`);
            fileInput.value = ''; // Reset input to allow retry
        }
    });

    function showError(message) {
        statusDiv.innerHTML = `⚠️ ${message}`;
        statusDiv.style.color = 'var(--error)';
    }
});
