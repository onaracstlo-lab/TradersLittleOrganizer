"""Build 626: release filename is published only after complete inspection."""
import hashlib
import pytest
import tlo_github_updates as U

pytestmark = pytest.mark.behavior
ASSET_NAME='TLO-v7-Windows-x64.zip'


def asset(contents=b'valid-binary'):
    return {'name': ASSET_NAME, 'browser_download_url': 'https://github.com/owner/repo/releases/download/test/thing',
            'size': len(contents), 'digest': 'sha256:'+hashlib.sha256(contents).hexdigest()}


def configure(monkeypatch, root, contents=b'valid-binary', verify_ok=True):
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(U, '_downloads_dir', lambda: root)
    def download(_asset, destination):
        assert destination.name.endswith('.pending')
        destination.write_bytes(contents)
        return True
    monkeypatch.setattr(U, '_download_asset', download)
    def inspect(path, **kwargs):
        if not verify_ok:
            raise ValueError('malformed ZIP')
        return {'databases_included': False, 'packaging_mode': 'test'}
    monkeypatch.setattr(U, '_inspect_downloaded_package', inspect)
    monkeypatch.setattr(U,'_update_download_settings',lambda *a,**k: '')


def invoke():
    return U._download_and_report_verified_asset(asset(), tlo_home=None, latest_build=626,
       asset_name=ASSET_NAME, package_kind='update', platform_key='windows')


def test_reject_malformed_without_publishing(tmp_path, monkeypatch):
    configure(monkeypatch,tmp_path,verify_ok=False)
    with pytest.raises(ValueError,match='malformed ZIP'): invoke()
    assert list(tmp_path.iterdir()) == []


def test_valid_package_published_atomically(tmp_path, monkeypatch):
    configure(monkeypatch,tmp_path)
    result=invoke()
    assert result.status == 'downloaded'
    assert (tmp_path/ASSET_NAME).read_bytes() == b'valid-binary'
    assert list(tmp_path.iterdir()) == [tmp_path/ASSET_NAME]


def test_conflicting_user_file_remains_unchanged(tmp_path,monkeypatch):
    configure(monkeypatch,tmp_path)
    dest=tmp_path/ASSET_NAME;dest.write_bytes(b'user-keeps-this')
    with pytest.raises(FileExistsError): invoke()
    assert dest.read_bytes() == b'user-keeps-this'


def test_reuse_existing_only_after_inspection(tmp_path,monkeypatch):
    configure(monkeypatch,tmp_path)
    dest=tmp_path/ASSET_NAME;dest.write_bytes(b'valid-binary')
    r=invoke();assert r.status=='already_downloaded'
    monkeypatch.setattr(U,'_inspect_downloaded_package',lambda *a,**k: (_ for _ in ()).throw(ValueError('bad ZIP')))
    with pytest.raises(ValueError,match='bad ZIP'):invoke()
    assert dest.read_bytes()==b'valid-binary'
