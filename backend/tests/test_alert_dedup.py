"""Alert dedup logic — pure-function helper smoke tests.

Real DB-backed dedup is exercised end-to-end in preflight_check.py.
"""

from app.services.alert_service import _employee_id_from_account


def test_account_to_employee_id_acc_prefix():
    assert _employee_id_from_account("ACC_00000001") == "EMP_00000001"


def test_account_to_employee_id_acct_prefix():
    assert _employee_id_from_account("ACCT_062946") == "EMP_062946"


def test_account_to_employee_id_unknown_prefix():
    assert _employee_id_from_account("XYZ_001") == "EMP_XYZ_001"
