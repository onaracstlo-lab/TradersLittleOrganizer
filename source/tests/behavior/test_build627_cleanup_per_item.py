"""Build 627: POSIX cleanup guards apply per deletion item, not globally."""
import os
import subprocess
import pytest
from tlo_inventory_update import _append_delete_command

pytestmark=pytest.mark.behavior


def test_mixed_volume_labels_skip_and_continue(tmp_path):
    script=tmp_path/'deleteBackupFolders.sh'
    wrong=tmp_path/'bad-volume'/'some folder'
    good=tmp_path/'good-volume'/'some folder'
    wrong.mkdir(parents=True);good.mkdir(parents=True)
    (wrong/'keep.txt').write_text('valuable')
    (good/'remove.txt').write_text('old')
    assert _append_delete_command(str(script),str(wrong),'Other Disk')
    assert _append_delete_command(str(script),str(good),'Correct Disk')
    stub=tmp_path/'bin';stub.mkdir()
    findmnt=stub/'findmnt'
    findmnt.write_text('#!/bin/sh\ncase "$*" in *good-volume*) echo "Correct Disk";; *) echo "Wrong Disk";; esac\n')
    findmnt.chmod(0o755)
    # The script prioritizes findmnt in this controlled environment.
    env=dict(os.environ,PATH=str(stub)+':'+os.environ.get('PATH',''))
    result=subprocess.run(['/bin/sh',str(script)],env=env,capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    assert wrong.exists() and (wrong/'keep.txt').exists()
    assert not good.exists()
    assert 'SKIPPED' in result.stderr
    assert 'deleted=1' in result.stdout and 'skipped=1' in result.stdout


def test_shell_escapes_names_and_never_deletes_unlabeled(tmp_path):
    script=tmp_path/'deleteBackupFolders.sh'
    target=tmp_path/'drive'/'show with dollar$and;quotes'
    target.mkdir(parents=True)
    assert _append_delete_command(str(script),str(target),'')
    result=subprocess.run(['/bin/sh',str(script)],capture_output=True,text=True)
    assert result.returncode == 0
    assert target.is_dir()
    assert 'skipped=1' in result.stdout
