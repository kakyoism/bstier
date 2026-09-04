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


def setup_function():
    # _serv_fact.setup_test_sandbox()
    pass


def teardown_function():
    # _serv_fact.teardown_test_sandbox()
    pass


def test_extract_from_deepdraft_matches_expected():
    args = types.SimpleNamespace(
        command='extract',
        fromPath=osp.join(_paths.caseOrgDir, 'bstier.png'),
        toPath=osp.join(_paths.caseGenDir, 'bstier.json'),
        source='deepdraft'
    )
    res, out = core.main(args)
    got = util.load_json(out.toPath)
    ref = util.load_json(osp.join(_paths.caseRefDir, 'bstier.json'))
    assert res.ok == True
    assert got == ref
