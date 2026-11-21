"""Build 705: risk-limited rename-date and Unicode identity regressions."""
import pytest
from tlo_rename_safety import safe_rename_target

pytestmark = pytest.mark.behavior


@pytest.mark.parametrize(('source','target'),[
 ('Wilco 98-05-08 Metro','Wilco 1998-05-08 Metro'),
 ('Wilco 8. Mai 1998 Metro','Wilco 1998-05-08 Metro'),
 ('Wilco 1er avril 1998 Metro','Wilco 1998-04-01 Metro'),
 ('Røyksopp 1998-05-08 Oslo','Royksopp 1998-05-08 Oslo'),
 ('Æther 1998-05-08 Oslo','AEther 1998-05-08 Oslo'),
])
def test_rename_guards_accept_equivalent_dates_and_latin_names(source, target):
    accepted, reason = safe_rename_target(source, target, date='1998-05-08')
    assert accepted == target, reason


@pytest.mark.parametrize(('source','target'),[
 ('Wilco 98-05-08 Metro 24-96','Wilco 1998-05-08 Metro'),
 ('Phish 1997-11-28 Worcester 101589','Phish 1997-11-28 Worcester'),
 ('Dead 1977-05-08 Ithaca','Dead 1977-05-09 Ithaca'),
 ('Wilco 97-05-08 Metro','Wilco 1998-05-08 Metro'),
 ('Кино 1990-06-24 Москва','Кино 1990-06-24'),
])
def test_rename_guards_still_refuse_identity_loss(source, target):
    accepted, reason = safe_rename_target(source, target, date='1998-05-08')
    assert not accepted, (source, reason)
