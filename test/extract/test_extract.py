"""
default folder structure: appdepth=3, repodepth=3
  - service_root: _cm.ancestorDirs[2]
    - test: _cm.ancestorDirs[1]
      - <case_dir>: _cm.ancestorDirs[0]
        - _org
        - _ref
        - _gen
"""
import glob
import os
import os.path as osp
import shutil
import types
import importlib

# 3rd party
import kkpyutil as util
import pytest

# project
_cm = util.init_repo(__file__, appdepth=3, repodepth=3)
_paths = types.SimpleNamespace(
    appRoot=_cm.ancestorDirs[2],
    caseDir=_cm.ancestorDirs[0],
)
_paths.appName = osp.basename(_paths.appRoot)
_paths.caseOrgDir = osp.join(_paths.caseDir, '_org')
_paths.caseGenDir = osp.join(_paths.caseDir, '_gen')
_paths.caseRefDir = osp.join(_paths.caseDir, '_ref')
core = importlib.import_module('core')
from extractors.common import assign_unique_candidates
from extractors.deepdraft import resolve_deepdraft_tier_labels
from extractors.labels import recognize_tier_label


def setup_function():
    # _serv_fact.setup_test_sandbox()
    pass


def teardown_function():
    # _serv_fact.teardown_test_sandbox()
    pass


def test_extract_from_deepdraft_matches_expected():
    args = types.SimpleNamespace(
        command='extract',
        fromPath=osp.join(_paths.caseOrgDir, 'deepdraft.png'),
        toPath=osp.join(_paths.caseGenDir, 'bstier.json'),
        source='deepdraft'
    )
    res, out = core.main(args)
    got = util.load_json(out.toPath)
    ref = util.load_json(osp.join(_paths.caseRefDir, 'bstier.json'))
    assert res.ok == True
    assert got == ref


def test_master_document_uses_injected_ocr_adapter():
    args = types.SimpleNamespace(
        command='extract',
        fromPath=osp.join(_paths.caseOrgDir, 'deepdraft.png'),
        toPath=None,
        source='deepdraft',
        master=True,
    )
    calls = []

    def fake_ocr(image_path):
        calls.append(image_path)
        return 'Brawi Stars Tier List — Pinball Dreams'

    worker = core.Worker(args, ocr_adapter=fake_ocr)
    document = worker._build_m1_document(
        {'S': ['gus', 'bull']},
        args.fromPath,
    )

    assert calls == [args.fromPath]
    assert document['map'] == 'pinballDreams'
    assert document['mode'] == 'brawlBall'
    assert document['originalTierlist'] == {'S': ['gus', 'bull']}


def test_tiermaker_extraction_builds_title_bearing_global_document(tmp_path):
    args = types.SimpleNamespace(
        command='extract',
        fromPath=osp.join(_paths.appRoot, 'res', 'example', 'tiermaker.jpg'),
        toPath=str(tmp_path / 'tiermaker.json'),
        source='tiermaker',
        title='June 2026',
        master=False,
    )
    labels = iter(('S', 'A', 'B', 'C', 'D', 'F'))
    worker = core.Worker(args, tier_label_adapter=lambda crop: next(labels))

    result, output = worker.main()
    document = util.load_json(output.toPath)

    assert result.ok is True
    assert result.detail == 'TierMaker global document generated.'
    assert document['title'] == 'June 2026'
    assert list(document['originalTierlist']) == ['S', 'A', 'B', 'C', 'D', 'F']
    assert document['originalTierlist']['S']
    assert document['tierColors']['S'].startswith('#')
    assert len(document['tierColors']['S']) == 7
    assert 'globalRoles' in document
    assert 'map' not in document
    assert 'mapRoles' not in document


def test_tiermaker_extraction_requires_title():
    args = types.SimpleNamespace(
        command='extract',
        fromPath=osp.join(_paths.appRoot, 'res', 'example', 'tiermaker.jpg'),
        toPath=None,
        source='tiermaker',
        title=None,
        master=False,
    )

    with pytest.raises(ValueError, match='--title'):
        core.Worker(args).validate_args()


def test_tiermaker_extraction_resolves_known_ambiguous_tiles(tmp_path):
    args = types.SimpleNamespace(
        command='extract',
        fromPath=osp.join(_paths.appRoot, 'res', 'example', 'tiermaker.jpg'),
        toPath=str(tmp_path / 'tiermaker.json'),
        source='tiermaker',
        title='June 2026',
        master=False,
    )
    labels = iter(('S', 'A', 'B', 'C', 'D', 'F'))
    worker = core.Worker(args, tier_label_adapter=lambda crop: next(labels))

    result, output = worker.main()
    document = util.load_json(output.toPath)

    assert result.ok is True
    assert document['originalTierlist']['A'][-2] == 'gene'
    assert document['originalTierlist']['C'][-8] == 'squeak'
    assert document['originalTierlist']['C'][-9] == 'sprout'
    assert document['originalTierlist']['D'][-5] == 'hank'
    names = [
        name
        for values in document['originalTierlist'].values()
        for name in values
    ]
    assert {'colt', 'otis'} <= set(names)
    assert len(names) == len(set(names))


def test_candidate_assignment_retries_displaced_tiles():
    selected = assign_unique_candidates([
        ('first', [(4, 'shared', 0), (3, 'fallback', 1)]),
        ('second', [(5, 'shared', 0), (4, 'other', 2)]),
    ], min_score=3)

    assert selected == {
        'first': (3, 'fallback'),
        'second': (5, 'shared'),
    }


def test_tier_label_uses_ocr_consensus_when_first_variant_is_wrong():
    assert recognize_tier_label(None, lambda crop: ['A', 'B', 'B', 'B', 'B', '7']) == 'B'


def test_deepdraft_label_resolution_repairs_s_plus_and_s_confusion():
    labels = ['S', 'S', 'A', 'B', 'C', 'D', 'F']

    assert resolve_deepdraft_tier_labels(labels) == [
        'S+', 'S', 'A', 'B', 'C', 'D', 'F']


def test_deepdraft_label_resolution_supports_s_max_without_s_plus():
    labels = ['S', 'A', 'B', 'S', 'D', 'F']

    assert resolve_deepdraft_tier_labels(labels) == [
        'S', 'A', 'B', 'C', 'D', 'F']


def test_deepdraft_label_resolution_repairs_misread_c_row():
    labels = ['S+', 'S', 'A', 'B', 'S', 'D', 'F']

    assert resolve_deepdraft_tier_labels(labels) == [
        'S+', 'S', 'A', 'B', 'C', 'D', 'F']


def test_deepdraft_label_resolution_keeps_ambiguous_duplicates():
    labels = ['S', 'S', 'A', 'B', 'S', 'D', 'F']

    assert resolve_deepdraft_tier_labels(labels) == labels
