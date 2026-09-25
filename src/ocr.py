"""OCR backend boundaries used by the source-specific extractors."""

import os
import subprocess
import tempfile

import cv2


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


class TesseractTierLabelAdapter:
    """Recognize a tier label from a cropped colored header panel."""

    def __init__(self, executable='tesseract', page_segmentation_mode=10):
        self.executable = executable
        self.page_segmentation_mode = page_segmentation_mode

    def __call__(self, crop):
        height, width = crop.shape[:2]
        center_crop = crop[
            int(height * 0.15):int(height * 0.85),
            int(width * 0.15):int(width * 0.85),
        ]
        channels = [center_crop[:, :, index] for index in range(3)]
        variants = []
        for channel in channels:
            variants.append(channel)
            variants.extend(
                cv2.threshold(channel, threshold, 255, cv2.THRESH_BINARY)[1]
                for threshold in (180, 200, 220, 240)
            )
        outputs = []
        for variant in variants:
            scaled = cv2.resize(
                variant, None, fx=8, fy=8, interpolation=cv2.INTER_CUBIC)
            path = None
            try:
                with tempfile.NamedTemporaryFile(
                        suffix='.png', delete=False) as temporary:
                    path = temporary.name
                cv2.imwrite(path, scaled)
                command = [
                    self.executable,
                    path,
                    'stdout',
                    '--psm',
                    str(self.page_segmentation_mode),
                    '-c',
                    'tessedit_char_whitelist=SABCDF+',
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
                if result.returncode == 0 and result.stdout.strip():
                    outputs.append(result.stdout.strip())
            finally:
                if path is not None:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass

        # PSM 13 is a useful fallback for the narrow F glyph, which PSM 10
        # can omit after the colored-panel background is removed. Keep this
        # crop tighter and omit the whitelist because Tesseract otherwise
        # tends to report the stylized F as a lowercase-looking character.
        fallback_crop = cv2.cvtColor(
            crop[int(height * 0.25):int(height * 0.75),
                 int(width * 0.25):int(width * 0.75)],
            cv2.COLOR_BGR2GRAY,
        )
        fallback = cv2.resize(
            fallback_crop, None, fx=8, fy=8, interpolation=cv2.INTER_CUBIC)
        path = None
        try:
            with tempfile.NamedTemporaryFile(
                    suffix='.png', delete=False) as temporary:
                path = temporary.name
            cv2.imwrite(path, fallback)
            result = subprocess.run(
                [
                    self.executable,
                    path,
                    'stdout',
                    '--psm',
                    '13',
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                outputs.append(result.stdout.strip())
        except OSError as exc:
            raise RuntimeError(
                f'Unable to execute OCR backend {self.executable!r}') from exc
        finally:
            if path is not None:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        return outputs