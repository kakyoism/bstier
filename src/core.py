import copy
import json
import logging
import os
import os.path as osp
import types
# 3rd party
import cv2
import kkpyutil as util
import numpy as np


def main(args):
    worker = Worker(args)
    return worker.main()


class Worker:
    def __init__(self, args):
        self.args = args
        self.res = types.SimpleNamespace(ok=False, detail='', advice='')
        self.out = None
        self.repo = util.init_repo(__file__, organization='kakyoism', repodepth=2)
        self.paths = types.SimpleNamespace(
            desktop=osp.join(util.get_platform_home_dir(), 'Desktop'),
            avatarDir=osp.join(self.repo.resDir, 'avatar'),
        )
        self.logger = self.repo.logger

    def main(self):
        self.args = self.validate_args()
        # depending on subcommand, perform tier list actions defined in cli.py
        if self.args.command == 'extract':
            return self._extract()
        elif self.args.command == 'generate':
            return self._generate()
        elif self.args.command == 'convert':
            return self._convert()
        else:
            self.res.detail = f"Unknown or unhandled command: {self.args.command}"
        return self.res, self.out

    def validate_args(self):
        fixed_args = copy.deepcopy(self.args)
        # Validate input path (--from) exists
        if fixed_args.fromPath:
            abs_from = osp.abspath(fixed_args.fromPath)
            if not osp.isfile(abs_from):
                raise FileNotFoundError(f"Input file not found: {abs_from}")
            fixed_args.fromPath = abs_from

        # Normalize output path if present
        if fixed_args.toPath:
            fixed_args.toPath = osp.abspath(fixed_args.toPath)
        return fixed_args

    def _extract(self):
        tier_pic = self.args.fromPath # "bstier.png"
        template_dir = self.paths.avatarDir
        threshold = 0.40

        # ==========================================
        # CONSTANT: Set this to your discovered scale 
        # after the first run (e.g., OPTIMAL_SCALE = 0.55)
        # Set to None to auto-calibrate on the first run.
        # ==========================================
        OPTIMAL_SCALE = 0.55 

        # 1. Load main image
        img = cv2.imread(tier_pic)
        if img is None:
            self.logger.error(f"ERROR: Could not load main tier list image from '{tier_pic}'")
            exit()

        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. Dynamic Boundary Detection
        _, thresh = cv2.threshold(img_gray, 80, 255, cv2.THRESH_BINARY)
        left_column = thresh[:, :120]
        contours, _ = cv2.findContours(left_column, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        valid_contours = [c for c in contours if cv2.contourArea(c) > 500]
        valid_contours = sorted(valid_contours, key=lambda c: cv2.boundingRect(c)[1])

        tier_names = ["S+", "S", "A", "B", "C", "D", "F"]
        tier_boundaries = {}

        for i, contour in enumerate(valid_contours):
            if i < len(tier_names):
                x, y, w, h = cv2.boundingRect(contour)
                tier_boundaries[tier_names[i]] = (y, y + h)

        results = {tier: [] for tier in tier_boundaries.keys()}
        template_files = [f for f in os.listdir(template_dir) if f.endswith(('.png', '.jpg'))]

        # If scale is not yet hardcoded, calibrate by finding the most frequently occurring best scale
        if OPTIMAL_SCALE is None:
            self.logger.info("Calibrating optimal scale across templates (runs only once)...")
            scale_votes = []
            scales_to_test = np.linspace(0.3, 1.0, num=15)
            
            # Sample up to 5 templates for quick calibration
            sample_templates = template_files[:5]
            for tf in sample_templates:
                template = cv2.imread(os.path.join(template_dir, tf), 0)
                if template is None: continue
                best_s, best_m = 1.0, 0
                for s in scales_to_test:
                    rw, rh = int(template.shape[1] * s), int(template.shape[0] * s)
                    if rw < 5 or rh < 5: continue
                    res = cv2.matchTemplate(img_gray, cv2.resize(template, (rw, rh)), cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    if max_val > best_m:
                        best_m, best_s = max_val, s
                scale_votes.append(best_s)
            
            OPTIMAL_SCALE = float(np.median(scale_votes))
            self.logger.info(f"\n>>> CALIBRATION COMPLETE! Hardcode this at the top of your script:")
            self.logger.info(f">>> OPTIMAL_SCALE = {OPTIMAL_SCALE:.2f}\n")

        # 3. Main Fast-Path Execution using the Global Constant Scale
        self.logger.info(f"Running extraction using fixed OPTIMAL_SCALE = {OPTIMAL_SCALE:.2f}...")
        matched_count = 0

        for template_file in template_files:
            brawler_name = os.path.splitext(template_file)[0].capitalize()
            template_path = os.path.join(template_dir, template_file)
            template = cv2.imread(template_path, 0)
            
            if template is None:
                continue
                
            rw = int(template.shape[1] * OPTIMAL_SCALE)
            rh = int(template.shape[0] * OPTIMAL_SCALE)
            
            if rw < 5 or rh < 5:
                continue
                
            resized_template = cv2.resize(template, (rw, rh))
            res = cv2.matchTemplate(img_gray, resized_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= threshold and max_loc is not None:
                x_match, y_match = max_loc
                for tier, (y_min, y_max) in tier_boundaries.items():
                    if y_min <= y_match < y_max:
                        if not any(b[2] == brawler_name for b in results[tier]):
                            results[tier].append((x_match, y_match, brawler_name))
                            matched_count += 1
                        break

        self.logger.info(f"Successfully matched {matched_count} out of {len(template_files)} brawlers.")

        # 4. Final Output in exact left-to-right layout order
        self.logger.info("\n--- Final Tier List Extraction ---")
        export_data = {}
        for tier, brawlers in results.items():
            brawlers.sort(key=lambda item: (item[1] // 40, item[0]))
            names_only = [b[2] for b in brawlers]
            export_data[tier] = names_only
            self.logger.info(f"{tier} Tier: {', '.join(names_only) if names_only else 'None'}")

        # Conditionally export to JSON if destination path is specified
        if self.args.toPath:
            util.save_json(self.args.toPath, export_data)
            self.logger.info(f"Successfully exported tier list to JSON: {self.args.toPath}")
            self.out = self.args.toPath
        
        self.res.ok = True
        self.res.detail = "Extraction routine executed."
        return self.res, self.out

    def _generate(self):
        self.res.ok = True
        self.res.detail = "Generation routine executed."
        return self.res, self.out

    def _convert(self):
        self.res.ok = True
        self.res.detail = "Conversion routine executed."
        return self.res, self.out
