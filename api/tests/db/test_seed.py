"""Los datos de desarrollo son ficticios, sin teléfonos, e idempotentes."""

from sqlalchemy import Connection, func, select
from sqlalchemy.orm import Session

from app.models import Invitacion, VersionRespuesta
from app.seed import seed


def test_seed_ficticio_e_idempotente(app_conn: Connection) -> None:
    s = Session(bind=app_conn, join_transaction_mode="create_savepoint")
    assert seed(s) == 5
    assert seed(s) == 0
    invs = s.scalars(select(Invitacion).order_by(Invitacion.codigo)).all()
    assert [i.codigo for i in invs] == ["INV-901", "INV-902", "INV-903", "INV-904", "INV-905"]
    assert all(i.telefono_principal is None and i.contacto_alterno_tel is None for i in invs)
    assert s.scalar(select(func.count()).select_from(VersionRespuesta)) == 1
