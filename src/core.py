import copy
import os.path as osp
import pathlib
import types
import kkpyutil as util


def main(args):
    worker = Worker(args)
    return worker.main()


class Worker:
    def __init__(self, args, ocr_adapter=None, tier_label_adapter=None):
        self.args = args
        self.ocr_adapter = ocr_adapter
        self.tier_label_adapter = tier_label_adapter
        self.res = types.SimpleNamespace(ok=False, detail='', advice='')
        self.out = types.SimpleNamespace(toPath='')
        self.repo = util.init_repo(__file__, organization='kakyoism', repodepth=2)
        self.paths = types.SimpleNamespace(
            desktop=osp.join(util.get_platform_home_dir(), 'Desktop'),
            avatarDir=osp.join(self.repo.resDir, 'avatar'),
            mapDir=osp.join(self.repo.resDir, 'map'),
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
        if (getattr(fixed_args, 'master', False)
                and getattr(fixed_args, 'source', None) != 'deepdraft'):
            raise ValueError('The --master option requires --source deepdraft')
        if (getattr(fixed_args, 'command', None) == 'extract'
                and getattr(fixed_args, 'source', None) == 'tiermaker'):
            title = getattr(fixed_args, 'title', '') or ''
            if not str(title).strip():
                raise ValueError(
                    'The --title option is required for TierMaker extraction')

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
        import ocr
        from extractors import ExtractionContext, create_extractor

        tier_pic = self.args.fromPath
        context = ExtractionContext(
            avatar_dir=pathlib.Path(self.paths.avatarDir),
            brawler_spec_path=pathlib.Path(
                osp.join(self.repo.resDir, 'spec', 'all.brawler.json')),
            tier_label_adapter=(
                self.tier_label_adapter or ocr.TesseractTierLabelAdapter()),
            logger=self.logger,
        )
        extractor = create_extractor(self.args.source, context)
        extracted = extractor.extract(tier_pic)
        export_data = extracted.tiers

        output_data = export_data
        if self.args.source == 'tiermaker':
            output_data = self._build_tiermaker_document(
                export_data, self.args.title, extracted.tier_colors)
        elif getattr(self.args, 'master', False):
            output_data = self._build_m1_document(export_data, tier_pic)

        # Conditionally export to JSON if destination path is specified
        if self.args.toPath:
            util.save_json(self.args.toPath, output_data)
            self.logger.info(f"Successfully exported tier list to JSON: {self.args.toPath}")
            self.out.toPath = self.args.toPath
        
        self.res.ok = True
        self.res.detail = (
            'M1 master document generated.'
            if getattr(self.args, 'master', False)
            else 'TierMaker global document generated.'
            if self.args.source == 'tiermaker'
            else 'Extraction routine executed.'
        )
        return self.res, self.out

    def _build_tiermaker_document(self, tierlist, title, tier_colors=None):
        import m1

        brawler_path = osp.join(self.repo.resDir, 'spec', 'all.brawler.json')
        global_roles = m1.load_global_roles(brawler_path)
        document = m1.build_global_document(tierlist, title, global_roles)
        if tier_colors:
            document['tierColors'] = tier_colors
        return document

    def _build_m1_document(self, tierlist, image_path):
        import m1
        import ocr

        map_path = osp.join(self.repo.resDir, 'spec', 'all.map.json')
        brawler_path = osp.join(self.repo.resDir, 'spec', 'all.brawler.json')
        map_catalog = util.load_json(map_path)
        global_roles = m1.load_global_roles(brawler_path)
        mode_roles = m1.load_mode_roles(brawler_path)
        adapter = self.ocr_adapter or ocr.TesseractMapTitleAdapter()
        return m1.build_master_document_from_ocr(
            tierlist,
            image_path,
            adapter,
            map_catalog,
            global_roles,
            mode_roles,
        )

    def _generate(self):
        import render

        document = util.load_json(self.args.fromPath)
        render.render_document(
            document,
            self.paths.avatarDir,
            self.args.toPath,
            getattr(self.args, 'reso', None),
            self.paths.mapDir,
        )
        self.out.toPath = self.args.toPath
        self.res.ok = True
        self.res.detail = 'Tierlist document rendered.'
        return self.res, self.out

    def _convert(self):
        self.res.ok = True
        self.res.detail = "Conversion routine executed."
        return self.res, self.out
