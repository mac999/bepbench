import os
import tempfile

import pytest

os.environ.setdefault("BEP_DATA_DIR", tempfile.mkdtemp(prefix="bep-test-"))

from bepkit.app import create_app  # noqa: E402
from bepkit.extensions import db  # noqa: E402


@pytest.fixture()
def app():
    application = create_app(testing=True)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def project(app):
    from bepkit import services

    return services.create_project("Test Plan", "iso19650", client="Acme", reference="T-001")
