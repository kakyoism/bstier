"""Small OCR backend boundary used by the Deep-Draft M1 pipeline."""

import subprocess


class TesseractMapTitleAdapter:
    """Run Tesseract on a tierlist image and return its raw OCR text."""

    def __init__(self, executable='tesseract', page_segmentation_mode=6):
        self.executable = executable
        self.page_segmentation_mode = page_segmentation_mode

    def __call__(self, image_path):
        command = [
            self.executable,
            str(image_path),
            'stdout',
            '--psm',
            str(self.page_segmentation_mode),
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise RuntimeError(
                f'Unable to execute OCR backend {self.executable!r}') from exc

        if result.returncode != 0:
            detail = result.stderr.strip()
            message = f'OCR backend failed with exit code {result.returncode}'
            if detail:
                message = f'{message}: {detail}'
            raise RuntimeError(message)

        text = result.stdout.strip()
        if not text:
            raise ValueError('OCR backend returned no text')
        return text