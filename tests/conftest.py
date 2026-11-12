"""Things many tests share."""

from __future__ import annotations

import pytest

from docassist import Document

TENANCY = """# Tenancy Agreement

This agreement is between the landlord, Mr Patel, and the tenant, Ms Jones.

The rent is £950 per month. Rent is paid on the first day of each month by bank transfer.

The deposit is £1,100. It is protected in a government approved deposit scheme within 30 days.

The tenant must give two months notice in writing to end the tenancy. The landlord must give at least two months notice.

Pets are not allowed without written permission from the landlord. Smoking is not allowed inside the property.
"""

PAYSLIP = """Understanding your payslip.

Your gross pay is what you earn before anything is taken off. Your net pay is what reaches your bank account.

Income tax is taken off through PAYE. Your tax code tells your employer how much you can earn before paying tax.

National Insurance is also taken off. It counts towards your state pension.

Pension contributions come out of your pay each month if you are in the workplace scheme.
"""


@pytest.fixture
def tenancy() -> Document:
    return Document.create("Tenancy agreement", TENANCY, "tenancy.md")


@pytest.fixture
def payslip() -> Document:
    return Document.create("Payslip guide", PAYSLIP, "payslip.txt")
